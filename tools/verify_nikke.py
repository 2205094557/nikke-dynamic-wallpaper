# -*- coding: utf-8 -*-
"""发布前全链路验收：起独立后端 → 下载 2 个角色（4.0/4.1 各一）→ 校验提取产物 →
导出动态壁纸并检查 project.json / 运行时版本 → 背景扩图工作流全链路。
任一 FAIL 非零退出禁止发布。

用法：python tools/verify_nikke.py [--clean]
（--clean：验收通过后删除本次下载的测试角色；无论是否 --clean，验收产生的
  壁纸项目 / 截图 / 扩图测试文件都会在结束时清理，不会污染用户已有导出）
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"
RES = ROOT / "resources"

FAILS: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> bool:
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + extra) if extra else ""))
    if not ok:
        FAILS.append(name)
    return ok


def wait_health(timeout: float = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/api/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    return False


def _verify_outpaint_workflow(target: dict) -> None:
    """扩图工作流验收：全程只动测试产物，结束后把新增文件清干净。

    官方背景图不在仓库内（resources/ 为本地素材），若本机没有背景图则跳过本段。
    """
    from PIL import Image  # 仅本段需要

    custom = RES / "custom"
    output = RES / "output"
    input_dir = RES / "input"
    preview = RES / "preview"
    thumbs = RES / "thumbnails" / "background"
    wallpapers = RES / "wallpapers"

    def snap(d: Path) -> set[str]:
        return {p.name for p in d.iterdir()} if d.is_dir() else set()

    before = {d: snap(d) for d in (custom, output, input_dir, thumbs)}
    created_projects: list[Path] = []
    tag = "zz_verify_outpaint"
    try:
        bg_list = requests.get(f"{BASE}/api/backgrounds", params={"ship": target["ship"]}, timeout=60).json()
        recs = bg_list.get("recommendations") or []
        pool = recs or [b["filename"] for b in bg_list.get("backgrounds") or []
                        if b.get("source") == "official"]
        if not pool:
            print("  [SKIP] 本机没有可用背景图（resources/background 为空），跳过扩图工作流")
            return
        check("背景列表含自定义分类", any(c.get("id") == "custom" for c in bg_list.get("categories") or []))

        # ① 导出当前背景到导出目录 output
        src_name = pool[0]
        r = requests.post(f"{BASE}/api/backgrounds/export-outpaint",
                          json={"filename": src_name}, timeout=60).json()
        check("导出扩图（复制到 output 目录）", bool(r.get("ok")) and (output / src_name).is_file(),
              str(r.get("error") or r.get("filename")))
        check("  同时备好 input 目录", input_dir.is_dir() and (r.get("inputDir") or "").endswith("input"))

        # ② 模拟外部扩图：横向扩宽后存为 jpg（同时验证非 png 自动转 png）
        with Image.open(output / src_name) as im:
            w, h = im.size
            small = im.convert("RGB").resize((max(64, w // 16), max(64, h // 16)))
        canvas = Image.new("RGB", (int(small.width * 1.6), small.height), (24, 34, 56))
        canvas.paste(small, (int(small.width * 0.3), 0))
        canvas.save(input_dir / f"{tag}.jpg", quality=92)
        # 反证用：同样放一份在 output，导入时不应被识别
        canvas.save(output / f"{tag}_onlyoutput.png")
        # 模拟误操作：把未扩图的原始导出也丢进了 input，应被识别为"没扩图"跳过
        shutil.copy2(output / src_name, input_dir / src_name)

        # ③ 导入自定义库
        imp = requests.post(f"{BASE}/api/backgrounds/import-outpaint", timeout=120).json()
        check("导入扩图结果（jpg 自动转 png）", f"{tag}.png" in (imp.get("imported") or []), str(imp))
        check("自定义背景落盘", (custom / f"{tag}.png").is_file())
        check("output 里的图片不会被导入（只识别 input）",
              f"{tag}_onlyoutput.png" not in (imp.get("imported") or [])
              and not (custom / f"{tag}_onlyoutput.png").exists(),
              f"imported={imp.get('imported')}")
        lst = requests.get(f"{BASE}/api/backgrounds", params={"ship": target["ship"]}, timeout=60).json()
        mine = [b for b in lst.get("backgrounds") or [] if b["filename"] == f"{tag}.png"]
        check("列表归类为 custom", bool(mine) and mine[0].get("source") == "custom"
              and mine[0].get("category") == "custom", str(mine[:1]))
        thumb_ok = bool(mine) and (thumbs / mine[0]["thumb"].split("/")[-1]).is_file()
        check("自定义缩略图已生成", thumb_ok)
        imp2 = requests.post(f"{BASE}/api/backgrounds/import-outpaint", timeout=120).json()
        check("重复导入幂等（不重复入库）", imp2.get("imported") == [], str(imp2.get("imported")))
        check("未扩图的原始导出副本被跳过（不遮罩官方背景）",
              not (custom / src_name).exists() and src_name in (imp.get("unchanged") or [])
              and src_name not in (imp.get("imported") or []),
              f"unchanged={imp.get('unchanged')} imported={imp.get('imported')}")

        # ④ 超分自定义背景
        up = requests.post(f"{BASE}/api/backgrounds/upscale",
                           json={"filename": f"{tag}.png", "scale": 2, "algorithm": "waifu2x"},
                           timeout=600).json()
        if not up.get("ok") and "引擎" in str(up.get("error")):
            print(f"  [SKIP] 未安装超分引擎，跳过超分校验：{up.get('error')}")
            up = {}
        else:
            check("超分自定义背景", bool(up.get("ok")) and up.get("filename", "").endswith("_preview.png"),
                  str(up.get("error") or up.get("filename")))
            if up.get("filename"):
                with Image.open(preview / up["filename"]) as im:
                    check("  超分产物尺寸为 2x", im.size == (canvas.width * 2, canvas.height * 2),
                          f"{im.size} vs {(canvas.width * 2, canvas.height * 2)}")

        # ⑤ 合成导出：自定义原图 / 超分产物，背景必须随项目进包且缩放写进 CSS
        cases = [(f"{tag}.png", 120), (up.get("filename"), 150)]
        for bgname, scale in cases:
            if not bgname:
                continue
            r = requests.post(f"{BASE}/api/export", json={
                "ship": target["ship"], "bundle": target["bundle"], "name": target["name"],
                "options": {"bg": "image", "bgImage": bgname, "bgScale": scale, "scale": 100,
                            "offsetX": 0, "offsetY": 0, "alignment": "center", "pose": "main"},
            }, timeout=180).json()
            proj = Path(r.get("project") or "")
            if proj.is_dir():
                created_projects.append(proj)
            label = "自定义原图" if bgname.endswith(f"{tag}.png") else "超分产物"
            check(f"导出壁纸[{label}]", bool(r.get("ok")) and (proj / "assets" / bgname).is_file(),
                  str(r.get("error") or ""))
            if proj.is_dir() and (proj / "index.html").exists():
                html = (proj / "index.html").read_text(encoding="utf-8")
                check(f"  [{label}] 背景入包并写入缩放",
                      f"url('assets/{bgname}')" in html and f"background-size: {scale}% auto" in html)

        # ⑥ 删除自定义背景后应从列表消失
        d = requests.post(f"{BASE}/api/backgrounds/delete-custom",
                          json={"filename": f"{tag}.png"}, timeout=60).json()
        check("删除自定义背景", bool(d.get("ok")), str(d.get("error") or ""))
        lst2 = requests.get(f"{BASE}/api/backgrounds", params={"ship": target["ship"]}, timeout=60).json()
        check("  删除后列表不再出现", not [b for b in lst2.get("backgrounds") or []
                                        if b["filename"] == f"{tag}.png"])
    finally:
        # 只删除本次新增的文件；preview 里用户既有的超分缓存不碰
        for p in created_projects:
            shutil.rmtree(p, ignore_errors=True)
        for d in (custom, output, input_dir, thumbs):
            for name in snap(d) - before[d]:
                f = d / name
                if f.is_file():
                    f.unlink()
        for f in preview.glob(f"*{tag}*"):
            f.unlink()
        for f in preview.glob(f"._import_{tag}*"):
            f.unlink()


def main() -> int:
    clean = "--clean" in sys.argv[1:]

    def snap(d: Path) -> set[str]:
        return {p.name for p in d.iterdir()} if d.is_dir() else set()

    # 验收会真的导出壁纸/截图：记录验收前的已有文件，结束时只删本次新增的
    before_wp = snap(RES / "wallpapers")
    before_ex = snap(RES / "exports")

    proc = subprocess.Popen(
        [sys.executable, "backend_server.py", str(PORT)],
        cwd=str(ROOT),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_health():
            print("[FAIL] 验收后端未就绪")
            return 1
        print("== 1) 下载两个角色（4.0/4.1 各一）==")
        targets = [
            {"ship": "拉毗", "bundle": "c010_02", "name": "拉毗 白色诺言", "expect": "4.0"},
            {"ship": "毒蛇", "bundle": "c112_03", "name": "毒蛇 街头朋克", "expect": "4.1"},
        ]
        for t in targets:
            r = requests.post(f"{BASE}/api/download", json=t, timeout=300)
            res = r.json()
            ok = bool(res.get("ok"))
            check(f"下载 {t['bundle']}", ok, str(res.get("error") or ""))
            if ok:
                check(f"  {t['bundle']} 姿势齐全", set(res.get("poses") or []) >= {"main"}, str(res.get("poses")))

        local = json.loads((ROOT / "resources" / "metadata" / "local_skins.json").read_text(encoding="utf-8"))
        by_p = {l["painting"]: l for l in local}
        for t in targets:
            l = by_p.get(t["bundle"])
            check(f"索引收录 {t['bundle']}", bool(l), "")
            if l:
                asset = l["asset"]
                poses = asset.get("poses") or {}
                check(f"  {t['bundle']} 记录版本 {t['expect']}", (poses.get("main") or {}).get("version") == t["expect"],
                      str((poses.get("main") or {}).get("version")))
                for pose, info in poses.items():
                    d = ROOT / "resources" / asset["dir"]
                    check(f"  {t['bundle']}/{pose} 文件齐全",
                          (d / info["skel"]).exists() and (d / info["atlas"]).exists(),
                          info["skel"])

        print("== 2) 导出动态壁纸（main 姿势）==")
        for t in targets:
            r = requests.post(f"{BASE}/api/export", json={
                "ship": t["ship"], "bundle": t["bundle"], "name": t["name"],
                "options": {"bg": "monet", "scale": 100, "offsetX": 0, "offsetY": 0,
                            "alignment": "center", "pose": "main"},
            }, timeout=120)
            ex = r.json()
            proj = Path(ex.get("project") or "")
            check(f"导出 {t['bundle']}", bool(ex.get("ok")) and proj.is_dir(), str(ex.get("error") or ""))
            if proj.is_dir():
                pj = json.loads((proj / "project.json").read_text(encoding="utf-8"))
                props = pj.get("general", {}).get("properties", {})
                check("  project.json 属性齐全",
                      all(k in props for k in ("scalectrl", "offsetx", "offsety", "alignment")))
                check("  combo 为标准格式",
                      isinstance(props.get("alignment", {}).get("value"), str)
                      and isinstance(props.get("alignment", {}).get("options"), list))
                html = (proj / "index.html").read_text(encoding="utf-8")
                want_rt = f"spine-webgl-{t['expect']}.js"
                have_rt = re.search(r'<script src="([^"]+\.js)"', html).group(1)
                check(f"  运行时版本 {want_rt}", have_rt == want_rt, have_rt)
                check("  无互动/语音残留", "bd2-interact" not in html and "VOICE_JSON" not in html)

        print("== 3) 背景扩图工作流（导出 → 外部扩图 → 导入 → 超分 → 合成导出）==")
        _verify_outpaint_workflow(targets[0])

        print()
        if FAILS:
            print(f"存在 {len(FAILS)} 个 FAIL，禁止发布：")
            for f in FAILS:
                print("  -", f)
            return 1
        if clean:
            for t in targets:
                requests.post(f"{BASE}/api/library/delete", json=t, timeout=60)
            print("已清理验收下载的测试角色（--clean）")
        print("全部 PASS，可以发布。")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()
        # 清理本次验收产生的壁纸项目与截图，保留用户已有导出
        for name in snap(RES / "wallpapers") - before_wp:
            shutil.rmtree(RES / "wallpapers" / name, ignore_errors=True)
        for name in snap(RES / "exports") - before_ex:
            f = RES / "exports" / name
            if f.is_file():
                f.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
