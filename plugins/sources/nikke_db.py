"""NIKKE DB 静态资源源：从 nikke-db（Cloudflare Pages）按需下载角色 Spine 资产。

资源 URL 规则（https://nikke-db-legacy.pages.dev/l2d/）：
  - 主立绘（大厅动画）：/l2d/<id>/<base>_00.skel|.atlas + atlas 引用的贴图
  - aim 姿势：/l2d/<id>/aim/<base>_aim_00.skel|.atlas + 贴图
  - cover 姿势：/l2d/<id>/cover/<base>_cover_00.skel|.atlas + 贴图

  base = 元数据中该 id 的 f 字段（事件/特殊角色文件名前缀与 id 不一致），无则等于 id。

注意：Cloudflare Pages 对不存在的路径也返回 200（HTML 错误页，约 24KB），
所以"文件是否存在"必须按内容判定（skel 含版本号、atlas 为文本、png 魔数），
不能只看状态码——否则会把错误页当资源落盘。
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import requests

from core.registry import SourcePlugin

# skel 二进制第 9 字节起是 null 结尾的版本串（如 "4.0.47"/"4.1.20"），
# 用正则在前 64 字节里取版本，兼容格式漂移
_SKEL_VERSION_RE = re.compile(rb"(\d+)\.(\d+)\.\d+")
_ATLAS_PAGE_RE = re.compile(r"^([^\r\n]+\.png)\s*$", re.M | re.I)


def _looks_html(data: bytes) -> bool:
    head = data[:16].lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html")


def _prefix(data: bytes, n: int = 64) -> bytes:
    return data[:n]


def _valid_skel(data: bytes) -> bool:
    return not _looks_html(data) and bool(_SKEL_VERSION_RE.search(_prefix(data)))


def _valid_atlas(data: bytes) -> bool:
    return not _looks_html(data) and len(data) > 0


def _valid_png(data: bytes) -> bool:
    return data[:4] == b"\x89PNG"


def _read_spine_version(path: Path) -> str:
    """从 skel 头部读 Spine 版本（如 "4.0"/"4.1"），失败返回 "4.1" 兜底。"""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
        m = _SKEL_VERSION_RE.search(head)
        if m:
            return f"{m.group(1).decode()}.{m.group(2).decode()}"
    except OSError:
        pass
    return "4.1"


def atlas_pages(text: str) -> list[str]:
    """Spine atlas 文本里的页面贴图名：只有非缩进、以 .png 结尾的行是页面名。

    区域（region）名也可能顶格，但不会以 .png 结尾，不会误收。
    贴图名可能带 UTF-8 BOM（\ufeff），必须剥离，否则拼进 URL 会 404。
    """
    pages = []
    for m in _ATLAS_PAGE_RE.finditer(text):
        name = m.group(1).strip().lstrip("\ufeff")
        if name and name not in pages:
            pages.append(name)
    return pages


class NikkeDBSource(SourcePlugin):
    id = "nikke_db"
    name = "nikke-db 资源站"

    BASE = "https://nikke-db-legacy.pages.dev"

    def __init__(self) -> None:
        self.proxy: str | None = None
        self.cache_dir: Path | None = None
        self._session: requests.Session | None = None

    # ---- 内部 ----
    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            if self.proxy:
                self._session.proxies = {"http": self.proxy, "https": self.proxy}
        return self._session

    def download_file(
        self,
        url: str,
        dest: Path,
        cancel_event=None,
        validate=None,
        retries: int = 3,
    ) -> bool:
        """下载单个文件到 dest：.part 断点续传 + 内容校验 + os.replace 原子落位。

        Cloudflare Pages 对缺失路径返回 200 + HTML 错误页，validate 按内容判定
        是否为有效资源；校验不过视为缺失（删 .part 返回 False）。
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        headers: dict[str, str] = {}
        if part.exists() and part.stat().st_size > 0:
            headers["Range"] = f"bytes={part.stat().st_size}-"
        for attempt in range(retries):
            try:
                r = self.session.get(url, headers=headers, timeout=(10, 60), stream=True)
                if r.status_code == 416:  # Range 超出文件尾：part 已完整
                    os.replace(part, dest)
                    return True
                if r.status_code == 206:
                    mode = "ab"
                elif r.status_code == 200:
                    mode = "wb"
                    part.unlink(missing_ok=True)
                else:
                    return False
                with open(part, mode) as f, r:
                    for chunk in r.iter_content(1 << 16):
                        if cancel_event is not None and cancel_event.is_set():
                            part.unlink(missing_ok=True)
                            return False
                        f.write(chunk)
                if validate is not None:
                    with open(part, "rb") as f:
                        ok = validate(_prefix(f.read(), 64))
                    if not ok:
                        part.unlink(missing_ok=True)
                        return False
                os.replace(part, dest)
                return True
            except (requests.RequestException, OSError):
                if cancel_event is not None and cancel_event.is_set():
                    part.unlink(missing_ok=True)
                    return False
                time.sleep(1 + attempt)
        return False

    def _pose_urls(self, skin_id: str, pose: str, stem: str) -> tuple[str, str, str]:
        """返回 (目录 URL, skel 文件名, atlas 文件名)。pose=main 在角色目录根。"""
        rel = "" if pose == "main" else pose + "/"
        url_dir = f"{self.BASE}/l2d/{skin_id}/{rel}"
        return url_dir, f"{stem}.skel", f"{stem}.atlas"

    # ---- 对外 ----
    def download_skin(
        self,
        skin_id: str,
        base: str,
        out_dir: Path,
        poses: tuple[str, ...] = ("main", "aim", "cover"),
        cancel_event=None,
        main_stem: str | None = None,
    ) -> dict:
        """下载一个角色的全部姿势（每姿势 skel+atlas+贴图），返回姿势清单与文件列表。

        main_stem：主立绘文件名前缀。站点规则：清单有 f 字段时直接用 f 当文件名
        （事件演出等，如 EventScene_staranis_03.skel）；无 f 时为 <id>_00。
        aim/cover 固定 <id>_aim_00 / <id>_cover_00。
        姿势缺失（错误页）直接跳过不报错；贴图页解析失败则该姿势标 incomplete。
        """
        out_dir = Path(out_dir)
        main_stem = main_stem or f"{base}_00"
        poses_found: dict[str, dict] = {}
        files: list[dict] = []
        for pose in poses:
            if pose == "main":
                stem = main_stem
            else:
                stem = f"{skin_id}_{pose}_00"
            url_dir, skel_name, atlas_name = self._pose_urls(skin_id, pose, stem)
            pose_dir = out_dir / pose

            d_skel = pose_dir / skel_name
            ok = self.download_file(url_dir + skel_name, d_skel, cancel_event, validate=_valid_skel)
            if not ok:
                continue  # 该姿势不存在
            d_atlas = pose_dir / atlas_name
            ok = self.download_file(url_dir + atlas_name, d_atlas, cancel_event, validate=_valid_atlas)
            if not ok:
                continue

            try:
                pages = atlas_pages(d_atlas.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pages = []
            complete = True
            for page in pages:
                ok = self.download_file(url_dir + page, pose_dir / page, cancel_event, validate=_valid_png)
                files.append({"path": f"{pose}/{page}", "ok": ok})
                if not ok:
                    complete = False
            poses_found[pose] = {
                "skel": f"{pose}/{skel_name}",
                "atlas": f"{pose}/{atlas_name}",
                "version": _read_spine_version(d_skel),
                "complete": complete,
            }
            files.append({"path": f"{pose}/{skel_name}", "ok": True})
            files.append({"path": f"{pose}/{atlas_name}", "ok": True})
        return {"poses": poses_found, "files": files}
