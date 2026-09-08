"""壁纸项目生成公共工具：模板渲染、project.json、背景样式。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from core.palette import extract_palette, find_palette_source, mode_css

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
WALLPAPER_LAYOUT = TEMPLATES / "wallpaper-layout.js"


def _vendor_file(name: str) -> Path:
    """运行时 JS 文件定位：开发版在 frontend/public/vendor，打包版在 frontend/dist/vendor（vite 把 public 复制到 dist）。"""
    for base in (ROOT / "frontend" / "public" / "vendor", ROOT / "frontend" / "dist" / "vendor"):
        p = base / name
        if p.exists():
            return p
    return ROOT / "frontend" / "public" / "vendor" / name


# NIKKE 的 skel 版本不统一（实测 4.0.47 与 4.1.20 混用）：导出器按该皮肤
# local_skins.json 记录的 spine_version（4.0/4.1）复制对应运行时进壁纸项目。
SPINE_RUNTIMES = {
    "4.0": _vendor_file("spine-webgl-4.0.js"),
    "4.1": _vendor_file("spine-webgl-4.1.js"),
}


def spine_runtime(version: str | None) -> Path:
    """按 skel 版本返回运行时 JS 文件；未知版本回退 4.1。"""
    key = ".".join(str(version or "4.1").split(".")[:2])  # "4.0"/"4.1"
    return SPINE_RUNTIMES.get(key, SPINE_RUNTIMES["4.1"])

# 与 wallpaper-layout.js 的 ALIGN_ORDER / project.json combo 选项顺序一致
ALIGN_NAMES = ["center", "left-top", "right-top", "left-bottom", "right-bottom"]
ALIGN_LABELS = ["居中", "左上", "右上", "左下", "右下"]

BG_STYLES = {
    "solid": "background: linear-gradient(180deg, #182438, #0b0f17);",
    "gradient": "background: linear-gradient(135deg, #1d3f6e, #0e1b33 55%, #13294d);",
    "monet": (
        "background: radial-gradient(60% 70% at 20% 25%, rgba(122,92,255,.35), transparent 60%),"
        "radial-gradient(55% 65% at 80% 20%, rgba(58,167,255,.3), transparent 60%),"
        "radial-gradient(70% 80% at 50% 95%, rgba(255,122,92,.22), transparent 60%),"
        "linear-gradient(160deg, #141b2e, #0b0f17);"
    ),
    "frost": (
        "background: radial-gradient(45% 55% at 30% 30%, rgba(58,167,255,.25), transparent 60%),"
        "radial-gradient(45% 55% at 75% 70%, rgba(122,92,255,.22), transparent 60%),"
        "linear-gradient(180deg, #101826, #0b0f17);"
    ),
    "star": (
        "background: radial-gradient(1.5px 1.5px at 20% 30%, rgba(255,255,255,.7), transparent 60%),"
        "radial-gradient(1.5px 1.5px at 60% 15%, rgba(255,255,255,.6), transparent 60%),"
        "radial-gradient(1.5px 1.5px at 80% 45%, rgba(255,255,255,.5), transparent 60%),"
        "radial-gradient(1.5px 1.5px at 40% 70%, rgba(255,255,255,.55), transparent 60%),"
        "radial-gradient(1.5px 1.5px at 90% 80%, rgba(255,255,255,.45), transparent 60%),"
        "linear-gradient(180deg, #101a2e, #080c14);"
    ),
}


def bg_css(bg: str) -> str:
    return BG_STYLES.get(bg, BG_STYLES["monet"])


def bg_css_for_skin(skin: dict, root, bg: str, bg_color: str | None = None) -> str:
    """预览与导出共用的背景 CSS：所有模式都优先按皮肤素材取色生成，取色失败才用固定样式。"""
    src = find_palette_source(skin, root)
    palette = extract_palette(src) if src else None
    if palette:
        return mode_css(bg, palette, solid_color=bg_color)
    if bg == "solid" and bg_color:
        return f"background: {bg_color};"
    return bg_css(bg)


def project_dir_name(ship: str, name: str) -> str:
    """生成安全的壁纸项目目录名。

    每次导出追加 8 位随机后缀：Wallpaper Engine 按"目录路径"记忆滑块覆盖值，
    同一目录重复导出会沿用旧覆盖值导致导出的偏移"不生效"。新目录 = 全新壁纸，
    首次推送即导出值，所见即所得。Windows 不允许目录名以空格/点结尾，也禁止
    <>:"/\\|?* 等字符。
    """
    raw = f"{ship}_{name}"
    cleaned = "".join(ch for ch in raw if ch not in '<>:"/\\|?*').rstrip(" .")
    return f"{cleaned or 'wallpaper'}_{uuid.uuid4().hex[:8]}"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def project_json(
    title: str,
    preview: str = "preview.gif",
    scale: int = 100,
    offset_x: int = 0,
    offset_y: int = 0,
    char_offset_x: int | None = None,
    char_offset_y: int | None = None,
    alignment: int = 0,
) -> dict:
    # 语义与预览一致：scale 为百分比（100 = 自适应），偏移为画布宽/高百分比
    scale_ctl = int(_clamp(scale, 20, 300))
    ox = int(_clamp(offset_x, -100, 100))
    oy = int(_clamp(offset_y, -100, 100))

    # 采用 Wallpaper Engine 编辑器自己保存的字段格式（editable/fraction/index/order），
    # 避免 WE 导入时对滑块 value 做二次换算/误写覆盖值。
    def slider(text: str, value: int, lo: int, hi: int, order: int, index: int) -> dict:
        return {
            "text": text,
            "type": "slider",
            "value": value,
            "min": lo,
            "max": hi,
            "editable": True,
            "fraction": False,
            "index": index,
            "order": order,
        }

    properties = {
        "scalectrl": slider("缩放", scale_ctl, 20, 300, 103, 3),
        "offsetx": slider("水平偏移", ox, -100, 100, 101, 1),
        "offsety": slider("垂直偏移", oy, -100, 100, 102, 2),
        "alignment": {
            "text": "对齐方式", "type": "combo",
            # WE combo 标准格式：value 是选中项的字符串值，options 是 {label,value} 对象数组。
            "value": (
                ALIGN_NAMES[alignment]
                if isinstance(alignment, int) and 0 <= alignment < len(ALIGN_NAMES)
                else str(alignment or "center")
            ),
            "options": [
                {"label": label, "value": name}
                for name, label in zip(ALIGN_NAMES, ALIGN_LABELS)
            ],
            # editable 必须为 true：WE 属性面板只显示 editable 的属性
            "editable": True,
            "index": 0,
            "order": 100,
        },
    }

    # 角色独立偏移（只移骨架，背景不动）：仅 Spine 壁纸提供该控件
    if char_offset_x is not None:
        properties["charoffsetx"] = slider("角色水平偏移", int(_clamp(char_offset_x, -100, 100)), -100, 100, 104, 4)
    if char_offset_y is not None:
        properties["charoffsety"] = slider("角色垂直偏移", int(_clamp(char_offset_y, -100, 100)), -100, 100, 111, 11)

    return {
        "file": "index.html",
        "general": {"properties": properties},
        "title": title,
        "type": "web",
        "preview": preview,
    }


def export_defaults(options: dict) -> dict:
    """把预览的缩放/偏移/对齐换算成壁纸 HTML 初始值（与预览语义一致）。"""
    scale = int(_clamp(int(options.get("scale", 100) or 100), 20, 300))
    ox = int(_clamp(int(options.get("offsetX", 0) or 0), -100, 100))
    oy = int(_clamp(int(options.get("offsetY", 0) or 0), -100, 100))
    cox = int(_clamp(int(options.get("charOffsetX", 0) or 0), -100, 100))
    coy = int(_clamp(int(options.get("charOffsetY", 0) or 0), -100, 100))
    # 背景图独立位移（%）：只移动背景图（预览 drawBg 同语义）；其他项目模板无
    # {{BG_OFFSET_*}} 占位时替换为 no-op，无副作用
    box = int(_clamp(int(options.get("bgOffsetX", 0) or 0), -100, 100))
    boy = int(_clamp(int(options.get("bgOffsetY", 0) or 0), -100, 100))
    align = options.get("alignment", 0)
    align_name = ALIGN_NAMES[align] if isinstance(align, int) and 0 <= align < len(ALIGN_NAMES) else str(align or "center")
    anim = options.get("animation") or ""
    return {
        "SCALE": str(scale),
        "OFFSET_X": str(ox),
        "OFFSET_Y": str(oy),
        "CHAR_OFFSET_X": str(cox),
        "CHAR_OFFSET_Y": str(coy),
        "BG_OFFSET_X": str(box),
        "BG_OFFSET_Y": str(boy),
        "ALIGNMENT": align_name,
        "ANIMATION": json.dumps(str(anim), ensure_ascii=False),
    }


def render_template(name: str, **replacements) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)
    return text
