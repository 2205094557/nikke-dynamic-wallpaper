# -*- coding: utf-8 -*-
"""构建 NIKKE 元数据：nikke-db 角色清单(l2d.json) + l2d/ 目录列表 → ships/skins/characters/avatars/pinyin。

数据源：
  - 角色清单：nikke-db-vue 仓库 src/utils/json/l2d.json（含 id/英文名/cn 中文名/f 文件名前缀）
  - 可下载目录：GitHub API 列出 l2d/ 下的角色文件夹（分页，2 页 1000）
  - 头像：站点 images/sprite/si_<base>_00_s.png（PNG 内容，存为 .jpg 后缀供前端 avatars/<f>.jpg 拼接）

用法：python tools/fetch_nikke_metadata.py [--no-avatars]
网络失败时回退本地缓存（resources/metadata/l2d.json / l2d_folders.json），不阻断后续索引。
"""

import json
import re
import sys
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MD = ROOT / "resources" / "metadata"
AVATARS = ROOT / "resources" / "avatars"

from core.pinyin_index import build_pinyin_index  # noqa: E402

L2D_SOURCES = [
    "https://raw.githubusercontent.com/nikke-db/nikke-db-vue/main/src/utils/json/l2d.json",
    "https://cdn.jsdelivr.net/gh/nikke-db/nikke-db-vue@main/src/utils/json/l2d.json",
]
L2D_DIR_API = "https://api.github.com/repos/Nikke-db/Nikke-db.github.io/contents/l2d"
SPRITE_BASE = "https://nikke-db-legacy.pages.dev/images/sprite"
MANIFEST_CACHE = MD / "l2d.json"
FOLDER_CACHE = MD / "l2d_folders.json"


def fetch_json(urls: list[str], timeout: int = 60):
    """依次尝试多个源，全部失败返回 None。"""
    for u in urls:
        try:
            r = requests.get(u, timeout=timeout)
            if r.status_code == 200 and r.content[:9] != b"<!DOCTYPE":
                return r.json()
        except Exception:  # noqa: BLE001
            continue
    return None


def fetch_l2d_folders() -> list[str]:
    """GitHub API 分页拉 l2d/ 目录下的角色文件夹名；失败返回 None。"""
    ids: list[str] = []
    for page in (1, 2):
        try:
            r = requests.get(f"{L2D_DIR_API}?per_page=1000&page={page}", timeout=60)
            if r.status_code != 200:
                break
            page_ids = [e["name"] for e in r.json() if e.get("type") == "dir"]
            if not page_ids:
                break
            ids.extend(page_ids)
        except Exception:  # noqa: BLE001
            break
    return ids or None


def display(entry: dict, *keys: str) -> str:
    for k in keys:
        v = (entry or {}).get(k)
        if v:
            return str(v)
    return ""


def base_id_of(entry_id: str, known: set[str]) -> str:
    """皮肤 id（c010_02）归并到基础角色 id（c010）；无基础条目的保持自身。"""
    m = re.match(r"^(.*)_\d+$", entry_id)
    if m and m.group(1) in known:
        return m.group(1)
    return entry_id


def download_avatars(ships: list[dict], bases: dict[str, str]) -> int:
    """下载各基础角色头像（si_<base>_00_s.png，PNG 内容存 .jpg 后缀）。

    returns: 本次新下载数量。已存在（>0 字节）跳过；站点缺失（HTML 错误页）跳过。
    """
    AVATARS.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for ship in ships:
        base = bases.get(ship["name"], "")
        if not base:
            continue
        dest = AVATARS / f"{base}.jpg"
        if dest.exists() and dest.stat().st_size > 0:
            continue
        try:
            r = requests.get(f"{SPRITE_BASE}/si_{base}_00_s.png", timeout=20)
            if r.status_code == 200 and r.content[:4] == b"\x89PNG":
                dest.write_bytes(r.content)
                downloaded += 1
        except Exception:  # noqa: BLE001
            continue
    return downloaded


def main() -> int:
    no_avatars = "--no-avatars" in sys.argv[1:]

    MD.mkdir(parents=True, exist_ok=True)
    # 1) 角色清单：联网拉取，失败回退缓存
    l2d = fetch_json(L2D_SOURCES)
    if l2d is None and MANIFEST_CACHE.exists():
        try:
            l2d = json.loads(MANIFEST_CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            l2d = None
    if l2d is None:
        print("FAIL 无法获取角色清单（联网失败且无本地缓存）", flush=True)
        return 1
    MANIFEST_CACHE.write_text(json.dumps(l2d, ensure_ascii=False), encoding="utf-8")

    # 2) 可下载目录列表：失败时用全部清单 id（下载器按内容校验兜底）
    folders = fetch_l2d_folders()
    if folders is None and FOLDER_CACHE.exists():
        try:
            folders = json.loads(FOLDER_CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            folders = None
    if folders:
        FOLDER_CACHE.write_text(json.dumps(folders, ensure_ascii=False), encoding="utf-8")
        print(f"l2d 目录列表: {len(folders)} 个", flush=True)

    # 3) 合并：清单条目 + 目录里有但清单缺名的条目（名字回退 id）
    by_id: dict[str, dict] = {}
    for e in l2d:
        by_id[str(e.get("id"))] = e
    if folders:
        for fid in folders:
            by_id.setdefault(fid, {"id": fid, "name": fid})
    entries = list(by_id.values())
    known = set(by_id)
    print(f"条目合计: {len(entries)}（清单 {len(l2d)} + 目录补充 {len(entries) - len(l2d)}）", flush=True)

    # 4) 归并出基础角色
    ships: list[dict] = []
    ships_by_name: dict[str, dict] = {}
    base_of_entry: dict[str, str] = {}
    for e in entries:
        base = base_id_of(str(e.get("id")), known)
        base_of_entry[str(e.get("id"))] = base
        if base not in ships_by_name:
            nm = display(e, "cn", "tw", "ko", "jp", "name") or str(e.get("id"))
            ships_by_name[base] = {
                "id": base,
                "name": nm,
                "en": display(e, "name") or nm,
                "costumes": [],
                "sort": len(ships),
            }
            ships.append(ships_by_name[base])
        # 基础角色条目自身的显示名优先
        if str(e.get("id")) == base:
            nm = display(e, "cn", "tw", "ko", "jp", "name") or str(e.get("id"))
            ships_by_name[base]["name"] = nm
            ships_by_name[base]["en"] = display(e, "name") or nm
        ships_by_name[base]["costumes"].append(str(e.get("id")))

    # 显示名去重：NIKKE 存在多个 id 同名（如 c010/c989/c990/c994 都叫 Rapi/拉毗，
    # 量产型变体），前端按 ship 显示名挂接皮肤，重名会串组——后出现的加 (id) 后缀。
    name_count: dict[str, int] = {}
    for ship in ships:
        name_count[ship["name"]] = name_count.get(ship["name"], 0) + 1
    seen: dict[str, int] = {}
    for ship in ships:
        nm = ship["name"]
        if name_count[nm] <= 1:
            continue
        seen[nm] = seen.get(nm, 0) + 1
        if seen[nm] > 1:
            ship["name"] = f"{nm} ({ship['id']})"
            ship["en"] = f"{ship['en']} ({ship['id']})"

    # 5) skins/characters：每条目一个可下载皮肤（type=spine）
    skins: list[dict] = []
    characters: list[dict] = []
    for idx, e in enumerate(entries):
        eid = str(e.get("id"))
        base = base_of_entry[eid]
        ship = ships_by_name[base]
        nm = display(e, "cn", "tw", "ko", "jp", "name") or eid
        skin = {
            "ship": ship["name"],
            "name": nm,
            "painting": eid,
            "bundle": eid,
            "type": "spine",
            "f": str(e.get("f") or ""),
            "sort": idx,
        }
        skins.append(skin)
        characters.append({"id": eid, **skin})

    # 6) 头像（可选）
    bases: dict[str, str] = {s["name"]: s["id"] for s in ships}
    if no_avatars:
        print("跳过头像下载（--no-avatars）", flush=True)
    else:
        n = download_avatars(ships, bases)
        print(f"头像: 新下载 {n} 个", flush=True)
    avatars_map = {s["name"]: s["id"] for s in ships}
    (MD / "avatars.json").write_text(
        json.dumps(avatars_map, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # 7) 落盘
    (MD / "ships.json").write_text(json.dumps(ships, ensure_ascii=False, indent=1), encoding="utf-8")
    (MD / "skins.json").write_text(json.dumps(skins, ensure_ascii=False, indent=1), encoding="utf-8")
    (MD / "characters.json").write_text(json.dumps(characters, ensure_ascii=False, indent=1), encoding="utf-8")
    build_pinyin_index(MD, ships, skins)

    print(f"ships: {len(ships)} / skins: {len(skins)} / pinyin: ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
