"""本地后端 API 服务：提供官方 CDN 下载等接口，供前端（浏览器/桌面）调用。

启动: python backend_server.py [端口]   （默认 8766）
"""

from __future__ import annotations

import json
import hashlib
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import Config  # noqa: E402
from core.library import Library  # noqa: E402
from core.locks import named_lock  # noqa: E402
from core.metadata import Metadata  # noqa: E402
from core.palette import extract_palette, fallback_palette, find_palette_source, mode_css  # noqa: E402
from core.registry import Registry  # noqa: E402
from core.we_integration import apply_wallpaper  # noqa: E402
from core.applog import setup_logging  # noqa: E402

registry = Registry(ROOT / "plugins").discover()
metadata = Metadata(ROOT / "resources" / "metadata")
library = Library(ROOT / "resources" / "library.db")
config = Config(ROOT / "resources" / "config.json")
src = registry.get("sources", "nikke_db")
if config.get("proxy"):
    src.proxy = config.get("proxy") or None
src.cache_dir = ROOT / "resources" / "metadata"
logger = setup_logging()

# ---- 下载阶段事件推送（SSE）：前端右下角卡片实时显示 下载/合成/同步 等阶段 ----
_EVENT_QUEUES: list[queue.Queue] = []
_EVENT_LOCK = threading.Lock()


def _broadcast(name: str, data: dict) -> None:
    payload = f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    with _EVENT_LOCK:
        for q in _EVENT_QUEUES:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass


def _emit_stage(stage: str, **extra) -> None:
    _broadcast("stage", {"stage": stage, **extra})

_META_MTIMES: dict[str, float] = {}
# 批量下载取消：前端带 download_id 发起下载，点取消时置位对应 Event，
# 下载循环按 chunk 检查，能快速停止正在进行的 CDN 下载（而非等整个文件下完）。
_CANCEL_LOCK = threading.Lock()
_CANCEL_EVENTS: dict[str, threading.Event] = {}


def _register_cancel(download_id: str) -> threading.Event:
    ev = threading.Event()
    with _CANCEL_LOCK:
        _CANCEL_EVENTS[download_id] = ev
    return ev


def _unregister_cancel(download_id: str) -> None:
    with _CANCEL_LOCK:
        _CANCEL_EVENTS.pop(download_id, None)


def cancel_download(download_id: str) -> bool:
    with _CANCEL_LOCK:
        ev = _CANCEL_EVENTS.get(download_id)
    if ev is not None:
        ev.set()
        return True
    return False
# 本地索引是共享文件，并发下载时多线程同时写会损坏/丢数据，必须串行化。
_INDEX_LOCK = named_lock("nk_local_index")
# run_tool 与提取器都会改写全局 sys.argv，必须共用同一把锁。
_TOOL_LOCK = named_lock("nk_sysargv")


def ensure_fresh_metadata() -> None:
    """每个请求前调用：元数据 JSON 被外部工具/脚本改动（mtime 变化）时自动重载，
    保证界面看到的数据和后端 API（下载/导出/取色）永远一致，不会出现
    "界面有皮肤、下载却说皮肤不存在"的旧内存数据问题。"""
    changed = False
    for name in ("ships.json", "skins.json", "local_skins.json"):
        p = ROOT / "resources" / "metadata" / name
        mt = p.stat().st_mtime if p.exists() else 0.0
        if _META_MTIMES.get(name) != mt:
            _META_MTIMES[name] = mt
            changed = True
    if changed:
        metadata.reload()
        refresh_library()


def refresh_library() -> None:
    library.import_metadata(metadata.ships(), metadata.skins(), metadata.local_skins())


refresh_library()


def get_config() -> dict:
    """返回当前配置（含代理设置）。"""
    return {"ok": True, "config": config.data}


def set_config(patch: dict) -> dict:
    """更新配置并立即生效（代理等）。"""
    patch = patch or {}
    if "proxy" in patch:
        proxy = (patch.get("proxy") or "").strip()
        config.set("proxy", proxy)
        src.proxy = proxy or None
    return {"ok": True, "config": config.data}


def resolve_skin(ship: str, bundle: str, name: str | None = None) -> dict | None:
    hits = [s for s in metadata.skins() if s.get("ship") == ship and s.get("bundle") == bundle]
    if not hits:
        return None
    if name is None:
        return hits[0]
    for s in hits:
        if s.get("name") == name:
            return s
    # 名字对不上（占位名/旧名）：仅当 ship+bundle 唯一候选时容忍，
    # 避免 DOA 联动等"同 key 多皮肤"误配。
    return hits[0] if len(hits) == 1 else None


def downloaded_with_painting() -> list[dict]:
    out = []
    for s in library.downloaded_skins():
        skin = resolve_skin(s["ship"], s["bundle"], s.get("name"))
        out.append({**s, "painting": (skin or {}).get("painting", "")})
    return out


def skin_files(skin: dict) -> list[Path]:
    """返回该皮肤对应的本地资源路径（extracted/spine/<id>，含全部姿势）。"""
    painting = skin.get("painting", "")
    stype = skin.get("type", "")
    e = ROOT / "resources" / "extracted"
    if stype == "spine":
        p = e / "spine" / painting
    else:
        p = e / "static" / painting
    return [p] if p.exists() else []


def delete_skin_files(ship: str, bundle: str, name: str | None = None) -> dict:
    skin = resolve_skin(ship, bundle, name)
    if not skin:
        return {"ok": False, "error": "皮肤不存在"}
    removed = [str(p) for p in skin_files(skin)]
    for p in skin_files(skin):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)
    run_tool("build_local_index", timeout=120)
    metadata.reload()
    refresh_library()
    return {"ok": True, "removed": removed}


def delete_skins_batch(items: list[dict]) -> dict:
    """批量删除皮肤：只删文件 + 语音联动检查一次，最后重建一次索引。

    逐个调用 delete_skin_files 时每个皮肤都会触发一次 build_local_index
    （全量扫描 extracted 目录），全选删除 N 个皮肤就是 N 次全量重建——这是
    「设置页全选删除很慢」的根源。批量版把索引重建从 O(N) 降到 1 次。
    """
    removed: list[str] = []
    failed: list[dict] = []
    for it in items or []:
        try:
            ship = it.get("ship", "")
            bundle = it.get("bundle", "")
            name = it.get("name")
            skin = resolve_skin(ship, bundle, name)
            if not skin:
                failed.append({"ship": ship, "bundle": bundle, "name": name, "error": "皮肤不存在"})
                continue
            for p in skin_files(skin):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                elif p.is_file():
                    p.unlink(missing_ok=True)
                else:
                    pass
                removed.append(str(p))
        except Exception as e:  # noqa: BLE001
            failed.append({"ship": it.get("ship"), "error": str(e)})

    run_tool("build_local_index", timeout=120)
    metadata.reload()
    refresh_library()
    return {
        "ok": not failed,
        "removed_count": len(removed),
        "failed": failed,
        "failed_count": len(failed),
    }


def clear_all_downloads() -> dict:
    removed = []
    for sub in ("extracted",):
        d = ROOT / "resources" / sub
        if d.is_dir():
            for child in d.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
                removed.append(str(child))
    run_tool("build_local_index", timeout=120)
    metadata.reload()
    refresh_library()
    return {"ok": True, "removed": removed}


def _read_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def run_tool(name: str, args: list[str] | None = None, timeout: int = 600) -> tuple[int, bytes, bytes]:
    """进程内运行 tools/ 下的脚本模块（打包后无法再用 sys.executable 起子进程）。

    tools 模块没有 __init__.py，按文件路径动态加载，避免引入包结构改动。
    """
    with _TOOL_LOCK:
        import contextlib
        import importlib.util
        import io

        path = ROOT / "tools" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"_pack_tool_{name}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        old_argv = sys.argv
        sys.argv = [name] + (args or [])
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = mod.main() or 0
        finally:
            sys.argv = old_argv
        out = buf.getvalue().encode("utf-8", "ignore")
        return rc, out, b""


def finish_metadata_update() -> None:
    """同步完成后重建本地索引并刷新内存元数据/资源库。"""
    run_tool("build_local_index", timeout=120)
    metadata.reload()
    refresh_library()


def run_metadata_update() -> dict:
    """重建 NIKKE 元数据：nikke-db 角色清单(l2d.json) → l2d/ 目录列表 → ships/skins/characters → 索引。

    manifest 步骤联网拉取 nikke-db 的角色清单（角色名/中文名/f 字段）与可下载目录列表；
    失败不阻断其余步骤（回退本地缓存），但会在结果里标为失败。
    任一步工具抛异常也只标 fail、不冒泡（工具崩了不该让整个接口 500）。
    """
    report: dict = {"ok": True, "steps": {}}
    for step, tool, timeout in (
        ("manifest", "fetch_nikke_metadata", 300),
    ):
        try:
            rc, out, err = run_tool(tool, timeout=timeout)
            report["steps"][step] = {
                "ok": rc == 0,
                "output": out.decode("utf-8", "ignore")[-3000:],
                "error": err.decode("utf-8", "ignore")[-800:],
            }
        except Exception as e:  # noqa: BLE001
            report["steps"][step] = {
                "ok": False,
                "output": "",
                "error": f"{type(e).__name__}: {e}"[:800],
            }
        if not report["steps"][step]["ok"]:
            report["ok"] = False
    try:
        finish_metadata_update()
    except Exception as e:  # noqa: BLE001
        report["ok"] = False
        report["finalize_error"] = f"{type(e).__name__}: {e}"[:800]
    return report


def local_skin_asset(ship: str, bundle: str, name: str | None = None) -> dict | None:
    hits = [
        loc for loc in metadata.local_skins()
        if loc.get("ship") == ship and loc.get("bundle") == bundle
    ]
    if not hits:
        return None
    if name is None:
        return hits[0].get("asset")
    for loc in hits:
        if loc.get("name") == name:
            return loc.get("asset")
    return hits[0].get("asset") if len(hits) == 1 else None


ALIGN_MAP = {
    "center": 0,
    "left-top": 1,
    "right-top": 2,
    "left-bottom": 3,
    "right-bottom": 4,
}


def _export_project(ship: str, bundle: str, name: str | None, options: dict) -> str:
    """生成 WE 壁纸项目，返回项目目录。"""
    skin = resolve_skin(ship, bundle, name)
    if not skin:
        raise ValueError(f"皮肤不存在: {ship}/{bundle}")
    asset = local_skin_asset(ship, bundle, name)
    if not asset:
        raise ValueError("该皮肤尚未下载，请先下载后再导出")
    stype = skin.get("type", "")
    if (options or {}).get("staticImage"):
        # 静态壁纸：前端预览截图已存档，强制走静态导出器（NIKKE 所有皮肤 type 都是 spine）
        stype = "static"
    if stype not in ("spine", "static"):
        raise ValueError(f"皮肤类型 {stype} 不支持导出壁纸")
    exporter = registry.get(
        "exporters",
        {"spine": "wallpaper_spine", "static": "wallpaper_static"}[stype],
    )
    if exporter is None:
        raise ValueError("导出插件未注册")
    opts = options or {}
    try:
        proj = exporter.export(
            {**skin, "asset": asset},
            {
                "root": str(ROOT),
                "bg": opts.get("bg", "monet"),
                "bgColor": opts.get("bgColor"),
                "scale": int(opts.get("scale", 100) or 100),
                "bgScale": int(opts.get("bgScale", 100) or 100),
                "offsetX": int(opts.get("offsetX", 0) or 0),
                "offsetY": int(opts.get("offsetY", 0) or 0),
                "charOffsetX": int(opts.get("charOffsetX", 0) or 0),
                "charOffsetY": int(opts.get("charOffsetY", 0) or 0),
                # 背景图独立位移（只移背景图，预览 drawBg 同语义）
                "bgOffsetX": int(opts.get("bgOffsetX", 0) or 0),
                "bgOffsetY": int(opts.get("bgOffsetY", 0) or 0),
                "alignment": ALIGN_MAP.get(str(opts.get("alignment", "center")), 0),
                "animation": opts.get("animation", ""),
                "animations": opts.get("animations") or [],
                # NIKKE：壁纸使用的姿势（main/aim/cover），导出时烘进壁纸项目
                "pose": opts.get("pose", "main"),
                # 静态壁纸：前端截图保存后传入的资源相对路径（resources/exports/...）
                "staticImage": opts.get("staticImage", ""),
            },
            str(ROOT / "resources" / "wallpapers"),
        )
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"导出失败: {e}") from e
    return proj


def export_skin(ship: str, bundle: str, name: str | None, options: dict) -> dict:
    """生成 WE 壁纸项目并打开所在文件夹（手动拖入 Wallpaper Engine）。"""
    try:
        proj = _export_project(ship, bundle, name, options)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    try:
        os.startfile(str(Path(proj)))  # noqa: S606
        opened = True
    except Exception as e:  # noqa: BLE001
        opened = False
        return {
            "ok": True,
            "project": proj,
            "opened": False,
            "error": f"导出成功但打开文件夹失败: {e}",
        }
    return {
        "ok": True,
        "project": proj,
        "opened": opened,
        "message": "导出完成，已打开项目文件夹，请把 index.html 拖入 Wallpaper Engine",
    }


def export_static_image(ship: str, bundle: str, name: str | None = None) -> dict:
    """把静态立绘原图导出为普通图片到 resources/exports/ 并打开文件夹。"""
    skin = resolve_skin(ship, bundle, name)
    if not skin:
        return {"ok": False, "error": f"皮肤不存在: {ship}/{bundle}"}
    if skin.get("type") != "static":
        return {"ok": False, "error": "仅静态立绘支持导出图片"}
    asset = local_skin_asset(ship, bundle, name)
    if not asset:
        return {"ok": False, "error": "该皮肤尚未下载，请先下载"}
    src = ROOT / "resources" / asset["dir"] / asset.get("image", "painting.png")
    if not src.exists():
        return {"ok": False, "error": f"未找到立绘文件: {src}"}
    out_dir = ROOT / "resources" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = "".join(ch for ch in f"{ship}_{skin.get('name', '')}" if ch not in '<>:"/\\|?*').rstrip(" .")
    dest = out_dir / f"{name or 'painting'}.png"
    shutil.copy2(src, dest)
    try:
        os.startfile(str(out_dir))  # noqa: S606
        opened = True
    except Exception:  # noqa: BLE001
        opened = False
    return {
        "ok": True,
        "path": str(dest),
        "opened": opened,
        "message": f"图片已导出：{dest.name}",
    }


def export_image_data(
    ship: str, bundle: str, name: str | None, data_url: str, index: int | None = None
) -> dict:
    """把前端截取的当前预览帧（PNG dataURL）保存为图片并打开文件夹。

    index 为动画序号（spine 导出时传入）：文件名用"角色名-序号"（如 企业-3.png），
    便于按动画归档截图；不传时保持"角色名_皮肤名.png"的旧命名。
    """
    import base64

    if not data_url or "," not in data_url:
        return {"ok": False, "error": "缺少图像数据"}
    try:
        png = base64.b64decode(data_url.split(",", 1)[1])
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "图像数据解析失败"}
    if not png.startswith(b"\x89PNG"):
        return {"ok": False, "error": "仅支持 PNG 截图"}
    out_dir = ROOT / "resources" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    if index:
        safe_ship = "".join(ch for ch in ship if ch not in '<>:"/\\|?*').rstrip(" .")
        clean = f"{safe_ship or 'ship'}-{int(index)}"
    else:
        clean = "".join(ch for ch in f"{ship}_{name or bundle}" if ch not in '<>:"/\\|?*').rstrip(" .")
    dest = out_dir / f"{clean or 'capture'}.png"
    dest.write_bytes(png)
    try:
        os.startfile(str(out_dir))  # noqa: S606
        opened = True
    except Exception:  # noqa: BLE001
        opened = False
    return {"ok": True, "path": str(dest), "opened": opened, "message": f"图片已导出：{dest.name}"}


def _cleanup_stale_exports(keep: str) -> int:
    """清理 resources/wallpapers 下与本次导出同角色同皮肤的旧项目目录。

    每次「导出并应用」成功后，删除同名壁纸（目录名同前缀 {ship}_{name}_）的
    旧导出——resources/wallpapers 是待应用的中转区，同壁纸只留最新一份即可；
    不同名壁纸（其他角色/皮肤）全部保留。keep 为本次项目路径（绝对或相对均可）。

    目录名格式：{ship}_{name}_{uuid8}，前缀 = 去掉末尾 _{uuid8} 的部分。
    """
    wp = ROOT / "resources" / "wallpapers"
    if not wp.is_dir():
        return 0
    keep_path = Path(keep).resolve()
    keep_name = keep_path.name
    prefix = re.sub(r"_[0-9a-f]{8}$", "", keep_name)
    removed = 0
    for child in wp.iterdir():
        if not child.is_dir():
            continue
        if child.resolve() == keep_path:
            continue
        # 同角色同皮肤：目录名去掉 _uuid8 后与本次前缀一致；不同名则保留
        if re.sub(r"_[0-9a-f]{8}$", "", child.name) != prefix:
            continue
        shutil.rmtree(child, ignore_errors=True)
        removed += 1
    if removed:
        print(f"[export] 已清理 {removed} 个同皮肤旧导出项目目录", flush=True)
    return removed


def apply_skin(ship: str, bundle: str, name: str | None, options: dict) -> dict:
    """导出并直接应用到 Wallpaper Engine（新副本 + openWallpaper，绕开编辑器导入路径）。"""
    try:
        proj = _export_project(ship, bundle, name, options)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    ok = apply_wallpaper(Path(proj))
    if not ok:
        return {
            "ok": False,
            "project": proj,
            "error": "应用失败：未找到 Wallpaper Engine 安装目录",
        }
    # 应用成功才清理旧导出（失败时保留旧导出，用户可能手动拖入本次项目）
    cleaned = _cleanup_stale_exports(proj)
    return {
        "ok": True,
        "project": proj,
        "cleaned": cleaned,
        "message": "已生成并应用壁纸，可在 Wallpaper Engine 中查看",
    }


def download_skin(skin: dict, cancel_event: threading.Event | None = None) -> dict:
    """NIKKE：从 nikke-db 静态站按需下载角色 Spine 资产（主/aim/cover 三姿势）。

    无解包环节——下载的 .skel/.atlas/.png 直接落盘 resources/extracted/spine/<id>/，
    然后重建本地索引刷新资源库。姿势缺失（站点无该资源）自动跳过不报错。
    """
    skin_id = (skin.get("painting") or "").lower()
    if not skin_id:
        return {"ok": False, "skin": skin, "downloaded": [], "error": "缺少角色 id"}
    # 站点规则：清单 f 字段存在时主文件名 = f（事件演出），否则 = <id>_00
    f = (skin.get("f") or "").strip()
    base = f or skin_id
    main_stem = f or f"{skin_id}_00"
    extracted_dir = ROOT / "resources" / "extracted" / "spine" / skin_id

    _emit_stage("正在下载", detail=skin_id)
    result = src.download_skin(
        skin_id, base, extracted_dir,
        poses=("main", "aim", "cover"),
        cancel_event=cancel_event,
        main_stem=main_stem,
    )
    if cancel_event is not None and cancel_event.is_set():
        return {
            "ok": False,
            "cancelled": True,
            "skin": skin,
            "downloaded": result["files"],
            "error": "下载已取消",
        }

    downloaded = result["files"]
    poses = result["poses"]
    if not poses:
        return {
            "ok": False,
            "skin": skin,
            "downloaded": downloaded,
            "error": f"资源站未找到该角色资源: {skin_id}",
        }

    # 重建本地索引并刷新资源库
    _emit_stage("正在同步本地索引")
    with _INDEX_LOCK:
        run_tool("build_local_index", timeout=120)
        metadata.reload()
        refresh_library()

    failed_items = [d for d in downloaded if not d.get("ok")]
    incomplete = [p for p, info in poses.items() if not info.get("complete")]
    result_payload: dict = {
        "ok": True,
        "skin": skin,
        "downloaded": downloaded,
        "poses": sorted(poses),
    }
    if failed_items:
        result_payload["error"] = f"部分文件下载失败: {len(failed_items)} 个"
    if incomplete:
        result_payload["incomplete"] = incomplete
    return result_payload


def open_wallpapers_dir() -> dict:
    """打开软件自己的壁纸输出目录（resources/wallpapers，存放导出的待用壁纸项目）。"""
    d = ROOT / "resources" / "wallpapers"
    d.mkdir(parents=True, exist_ok=True)
    os.startfile(str(d))  # noqa: S606
    return {"ok": True, "path": str(d)}


def clean_exports() -> dict:
    """清理导出的壁纸项目与截图（resources/wallpapers + resources/exports）。"""
    removed = []
    for sub in ("wallpapers", "exports"):
        d = ROOT / "resources" / sub
        if d.is_dir():
            for child in d.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
                removed.append(str(child))
    return {"ok": True, "removed": len(removed)}


class Handler(BaseHTTPRequestHandler):
    def _query(self, key: str, default: str = "") -> str:
        """解析查询串 ?key=value。"""
        qs = self.path.split("?", 1)[1] if "?" in self.path else ""
        for part in qs.split("&"):
            k, _, v = part.partition("=")
            if k == key:
                return v
        return default

    def _send(self, status: int, payload: dict) -> None:
        # 诊断日志：记录前端每次 API 调用的请求与响应（真实窗口排障用）
        try:
            print(
                f"[api] {self.command} {self.path} -> {status} "
                f"{json.dumps(payload, ensure_ascii=False)[:300]}",
                flush=True,
            )
        except Exception:  # noqa: BLE001
            pass
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream_events(self) -> None:
        """SSE 长连接：把下载/提取/同步等阶段事件推送给前端。"""
        q: queue.Queue = queue.Queue(maxsize=200)
        with _EVENT_LOCK:
            _EVENT_QUEUES.append(q)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"event: connected\ndata: {}\n\n")
            self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=30)
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")  # 心跳保活
                    self.wfile.flush()
        except Exception:  # noqa: BLE001
            pass
        finally:
            with _EVENT_LOCK:
                if q in _EVENT_QUEUES:
                    _EVENT_QUEUES.remove(q)

    def _is_local_request(self) -> bool:
        """只允许本机页面调用后端：Host 必须为本机地址，且 Origin（浏览器跨站请求必带）
        若存在也必须是本机。这样即使网页被浏览器打开的其他恶意网站请求，也会被拒绝，
        避免恶意网页借本机 API 删除下载/触发下载占满磁盘。"""
        host = (self.headers.get("Host") or "").split(":", 1)[0].strip().lower()
        if host not in ("127.0.0.1", "localhost", "::1"):
            return False
        origin = self.headers.get("Origin") or ""
        if not origin:
            return True  # 同源请求 / 非浏览器客户端（curl、pywebview 等）
        from urllib.parse import urlparse

        return (urlparse(origin).hostname or "").lower() in ("127.0.0.1", "localhost", "::1")

    def _guard_local(self) -> bool:
        """非本机请求时直接返回 403，返回 False 表示调用方应停止处理。"""
        if self._is_local_request():
            return True
        self._send(403, {"ok": False, "error": "forbidden: 仅允许本机调用"})
        return False

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self._guard_local():
            return
        self._send(200, {"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        if not self._guard_local():
            return
        try:
            ensure_fresh_metadata()
            if self.path.startswith("/api/events"):
                self._stream_events()
                return
            if self.path.startswith("/api/health"):            self._send(200, {"ok": True, "plugins": registry.summary()})
            elif self.path.startswith("/api/library/downloaded"):
                self._send(200, {"ok": True, "skins": downloaded_with_painting()})
            elif self.path.startswith("/api/config"):
                self._send(200, get_config())
            else:
                self._send(404, {"ok": False, "error": "not found"})
        except Exception:  # noqa: BLE001
            logger.exception("GET %s failed", self.path)
            try:
                self._send(500, {"ok": False, "error": "internal error"})
            except Exception:  # noqa: BLE001
                pass

    def do_POST(self) -> None:  # noqa: N802
        if not self._guard_local():
            return
        try:
            ensure_fresh_metadata()
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
            if self.path.startswith("/api/"):
                print(
                    f"[api] POST {self.path} body={json.dumps(data, ensure_ascii=False)[:200]}",
                    flush=True,
                )
            if self.path.startswith("/api/download/cancel"):
                cancel_download(data.get("download_id") or "")
                self._send(200, {"ok": True})
            elif self.path.startswith("/api/download"):
                ship = data.get("ship")
                bundle = data.get("bundle")
                name = data.get("name")
                download_id = data.get("download_id") or ""
                skin = resolve_skin(ship, bundle, name)
                if not skin:
                    self._send(404, {"ok": False, "error": f"皮肤不存在: {ship}/{bundle}"})
                    return
                cancel_event = _register_cancel(download_id) if download_id else None
                try:
                    result = download_skin(skin, cancel_event)
                finally:
                    if download_id:
                        _unregister_cancel(download_id)
                self._send(200, result)
            elif self.path.startswith("/api/library/delete"):
                self._send(
                    200,
                    delete_skin_files(
                        data.get("ship"), data.get("bundle"), data.get("name")
                    ),
                )
            elif self.path.startswith("/api/library/delete-batch"):
                # 批量删除：items=[{ship,bundle,name},...]，只重建一次索引（快）
                items = data.get("items") or []
                if not isinstance(items, list) or not items:
                    self._send(400, {"ok": False, "error": "items 为空"})
                else:
                    self._send(200, delete_skins_batch(items))
            elif self.path.startswith("/api/library/clear"):
                self._send(200, clear_all_downloads())
            elif self.path.startswith("/api/metadata/update"):
                self._send(200, run_metadata_update())
            elif self.path.startswith("/api/config"):
                self._send(200, set_config(data.get("config") or {}))
            elif self.path.startswith("/api/log"):
                # 前端运行时错误上报（排障用）：打印到 stdout，不落盘
                print(f"[fe-error] {json.dumps(data, ensure_ascii=False)[:800]}", flush=True)
                self._send(200, {"ok": True})
            elif self.path.startswith("/api/export-image-data"):
                self._send(
                    200,
                    export_image_data(
                        data.get("ship"),
                        data.get("bundle"),
                        data.get("name"),
                        data.get("dataUrl") or "",
                        index=data.get("index"),
                    ),
                )
            elif self.path.startswith("/api/export-image"):
                self._send(
                    200,
                    export_static_image(data.get("ship"), data.get("bundle"), data.get("name")),
                )
            elif self.path.startswith("/api/export"):
                self._send(
                    200,
                    export_skin(
                        data.get("ship"),
                        data.get("bundle"),
                        data.get("name"),
                        data.get("options") or {},
                    ),
                )
            elif self.path.startswith("/api/apply"):
                self._send(
                    200,
                    apply_skin(
                        data.get("ship"),
                        data.get("bundle"),
                        data.get("name"),
                        data.get("options") or {},
                    ),
                )
            elif self.path.startswith("/api/palette"):
                ship = data.get("ship")
                bundle = data.get("bundle")
                name = data.get("name")
                mode = data.get("mode") or "auto"
                bg_color = data.get("bgColor")
                skin = resolve_skin(ship, bundle, name)
                asset = local_skin_asset(ship, bundle, name)
                if not skin or not asset:
                    self._send(200, {"ok": False, "error": "皮肤不存在或未下载"})
                else:
                    src = find_palette_source({**skin, "asset": asset}, ROOT)
                    palette = extract_palette(src) if src else None
                    css = mode_css(mode, palette, solid_color=bg_color)
                    self._send(
                        200,
                        {
                            "ok": bool(palette),
                            "colors": palette or fallback_palette(),
                            "source": str(src) if src else None,
                            "css": css,
                        },
                    )
            elif self.path.startswith("/api/open/download-dir"):
                os.startfile(str(ROOT / "resources" / "extracted"))  # noqa: S606
                self._send(200, {"ok": True})
            elif self.path.startswith("/api/open/extracted-dir"):
                os.startfile(str(ROOT / "resources" / "extracted"))  # noqa: S606
                self._send(200, {"ok": True})
            elif self.path.startswith("/api/open/wallpapers-dir"):
                self._send(200, open_wallpapers_dir())
            elif self.path.startswith("/api/library/clean-exports"):
                self._send(200, clean_exports())
            else:
                self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:  # noqa: BLE001
            logger.exception("POST %s failed", self.path)
            self._send(500, {"ok": False, "error": str(e)})

    def log_message(self, *args) -> None:  # noqa: D401
        pass


def main(port: int = 8766) -> None:
    """启动后端 API 服务。

    注意：打包版/桌面版会以线程方式调用 main(8770) 传入端口，
    因此这里**不再**从 sys.argv 读端口（之前会被启动参数意外覆盖，
    导致前端连不上后端）。
    """
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"backend API listening on http://127.0.0.1:{port}")
    logger.info("backend API listening on http://127.0.0.1:%s", port)
    server.serve_forever()


if __name__ == "__main__":
    _port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    main(_port)
