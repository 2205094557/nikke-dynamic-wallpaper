# -*- coding: utf-8 -*-
"""发布前全链路验收：起独立后端 → 下载 2 个角色（4.0/4.1 各一）→ 校验提取产物 →
导出动态 + 静态壁纸 → 检查 project.json / 运行时版本。任一 FAIL 非零退出禁止发布。

用法：python tools/verify_nikke.py [--clean]   （--clean：验收通过后清空测试数据）
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


def main() -> int:
    clean = "--clean" in sys.argv[1:]
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

        print("== 3) 导出静态壁纸（预览截图）==")
        png_1px = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9aw"
                   "AAAABJRU5ErkJggg==")
        r = requests.post(f"{BASE}/api/export-image-data", json={
            "ship": targets[0]["ship"], "bundle": targets[0]["bundle"], "name": targets[0]["name"],
            "dataUrl": f"data:image/png;base64,{png_1px}"}, timeout=60)
        saved = r.json()
        fname = (saved.get("path") or "").split("\\")[-1].split("/")[-1]
        check("截图存档", bool(saved.get("ok")) and bool(fname), str(saved.get("path")))
        r = requests.post(f"{BASE}/api/export", json={
            "ship": targets[0]["ship"], "bundle": targets[0]["bundle"], "name": targets[0]["name"],
            "options": {"bg": "monet", "scale": 100, "offsetX": 0, "offsetY": 0,
                        "alignment": "center", "staticImage": f"exports/{fname}"},
        }, timeout=120)
        ex = r.json()
        proj = Path(ex.get("project") or "")
        check("静态壁纸导出", bool(ex.get("ok")) and (proj / "index.html").exists(), str(ex.get("error") or ""))
        if proj.is_dir():
            html = (proj / "index.html").read_text(encoding="utf-8")
            check("  静态壁纸引用截图", f"assets/{fname}" in html)

        print()
        if FAILS:
            print(f"存在 {len(FAILS)} 个 FAIL，禁止发布：")
            for f in FAILS:
                print("  -", f)
            return 1
        print("全部 PASS，可以发布。")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
