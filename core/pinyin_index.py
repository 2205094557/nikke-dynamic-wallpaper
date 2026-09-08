"""拼音检索索引（pinyin.json）构建：元数据构建与本地索引共用。"""

from __future__ import annotations

import json
from pathlib import Path


def build_pinyin_index(md_dir: Path, ships: list[dict], skins: list[dict]) -> None:
    """生成检索索引 pinyin.json。

    NIKKE 名字本地化为中文：p 字段 = 中文名全拼 + 英文名原串（均可搜），
    i = 首字母；角色级并入 en 名。
    """
    md_dir = Path(md_dir)

    def py_of(text: str) -> str:
        if not text:
            return ""
        try:
            from pypinyin import lazy_pinyin

            return "".join(lazy_pinyin(text)).lower()
        except Exception:  # noqa: BLE001  无 pypinyin 时退化为原名
            return ""

    def key_of(*names: str) -> dict:
        cn_heads: list[str] = []
        latins: list[str] = []
        for n in names:
            n = (n or "").strip()
            if not n:
                continue
            head = n.split("·", 1)[0]  # 去掉「· 能力后缀」等
            if any("\u4e00" <= ch <= "\u9fff" for ch in head):
                cn_heads.append(head)
            else:
                latins.append("".join(ch for ch in head.lower() if ch.isalnum()))
        pys = [py_of(h) for h in cn_heads]
        p = "".join(pys) + "".join(latins)
        i = "".join(x[:1] for x in pys) + "".join(l[:1] for l in latins if l)
        return {"p": p[:64], "i": i[:16] or p[:8]}

    ships_map = {}
    for s in ships:
        nm = s.get("name", "")
        if nm:
            ships_map[nm] = key_of(nm, s.get("en", ""))
    skins_map: dict[str, dict] = {}
    for sk in skins:
        n = sk.get("name", "")
        if n and n not in skins_map:
            skins_map[n] = key_of(n)
    (md_dir / "pinyin.json").write_text(
        json.dumps({"ships": ships_map, "skins": skins_map}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
