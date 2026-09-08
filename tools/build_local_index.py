# -*- coding: utf-8 -*-
"""扫描 resources/extracted → 生成 local_skins.json（NIKKE 版）。

NIKKE 每个角色目录（extracted/spine/<id>/）含 main/aim/cover 三个姿势，
每姿势一组 skel+atlas+贴图；asset 记录 poses 映射 + 各姿势 Spine 版本
（4.0/4.1，运行时与壁纸导出按版本选对应 spine-webgl）。
"""
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MD = ROOT / "resources" / "metadata"
EXTRACTED = ROOT / "resources" / "extracted"

from core.pinyin_index import build_pinyin_index  # noqa: E402

_SKEL_VERSION_RE = re.compile(rb"(\d+)\.(\d+)\.\d+")

POSES = ("main", "aim", "cover")


def read_spine_version(path: Path) -> str:
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


def poses_asset(d: Path) -> dict | None:
    """收集角色目录下各姿势的 skel+atlas 成组（每姿势取第一个 skel 组）。"""
    poses: dict[str, dict] = {}
    for pose in POSES:
        pd = d / pose
        if not pd.is_dir():
            continue
        skels = sorted(pd.glob("*.skel"))
        if not skels:
            continue
        sk = skels[0]
        atlas = pd / (sk.stem + ".atlas")
        if not atlas.exists():
            continue
        poses[pose] = {
            "skel": f"{pose}/{sk.name}",
            "atlas": f"{pose}/{atlas.name}",
            "version": read_spine_version(pd / sk.name),
        }
    if not poses:
        return None
    main = poses.get("main") or poses[sorted(poses)[0]]
    return {
        "dir": "extracted/spine/" + d.name,
        # layers 兼容既有导出器（默认取主姿势）
        "layers": [{"skel": main["skel"], "atlas": main["atlas"]}],
        "poses": poses,
        "spine_version": main["version"],
    }


def main() -> int:
    try:
        skins = json.loads((MD / "skins.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        skins = []
    try:
        ships = json.loads((MD / "ships.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        ships = []
    by_painting = {}
    for s in skins:
        p = s.get("painting", "")
        if p and p not in by_painting:
            by_painting[p] = s

    local = []
    spine_dir = EXTRACTED / "spine"
    if spine_dir.is_dir():
        for d in sorted(spine_dir.iterdir()):
            if not d.is_dir():
                continue
            info = by_painting.get(d.name)
            if not info:
                continue
            asset = poses_asset(d)
            if not asset:
                continue
            local.append({
                "ship": info["ship"], "bundle": info["bundle"], "name": info["name"],
                "type": "spine", "painting": info.get("painting", d.name),
                "asset": asset,
            })

    local.sort(key=lambda x: (x["ship"], x["bundle"]))
    (MD / "local_skins.json").write_text(json.dumps(local, ensure_ascii=False, indent=2), encoding="utf-8")
    build_pinyin_index(MD, ships, skins)
    print("local_skins:", len(local))
    for l in local:
        poses = " ".join(sorted((l["asset"].get("poses") or {})))
        print(" ", l["ship"], "|", l["bundle"], "|", l["name"], "|", l["asset"]["dir"], "|", poses, "|", l["asset"].get("spine_version"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
