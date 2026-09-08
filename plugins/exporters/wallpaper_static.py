"""静态立绘壁纸导出插件：把预览截取的 PNG 生成为 WE web 壁纸项目。

NIKKE 无现成静态立绘文件，静态壁纸 = 用户在预览里截取的当前帧
（前端 export-image-data 保存到 resources/exports/ 后把相对路径随 options.staticImage 传入）。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from core.registry import ExporterPlugin
from core.wallpaper import (
    bg_css_for_skin,
    export_defaults,
    project_dir_name,
    project_json,
    render_template,
)


class WallpaperStaticExporter(ExporterPlugin):
    id = "wallpaper_static"
    name = "静态立绘壁纸导出"

    def export(self, skin: dict, options: dict, out_dir: str) -> str:
        static_image = (options.get("staticImage") or "").strip()
        if not static_image:
            raise ValueError("缺少静态图片（请先在预览中截图）")
        src = Path(options["root"]) / "resources" / static_image
        if not src.is_file():
            raise ValueError(f"未找到截图文件: {src}")

        out = Path(out_dir)
        proj = out / project_dir_name(skin["ship"], skin["name"])
        assets = proj / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        image = src.name
        shutil.copy2(src, assets / image)

        html = render_template(
            "wallpaper_static.html",
            IMAGE="assets/" + image,
            BG_CSS=bg_css_for_skin(
                skin, options.get("root"), options.get("bg", "monet"), options.get("bgColor")
            ),
            **export_defaults(options),
        )
        (proj / "index.html").write_text(html, encoding="utf-8")
        (proj / "project.json").write_text(
            json.dumps(
                project_json(
                    f"{skin['ship']} · {skin['name']}",
                    scale=options.get("scale", 100),
                    offset_x=options.get("offsetX", 0),
                    offset_y=options.get("offsetY", 0),
                    alignment=options.get("alignment", 0),
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(proj)
