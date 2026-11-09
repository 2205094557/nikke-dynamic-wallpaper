"""Spine 壁纸导出插件：生成 WE web 壁纸项目（base64 内嵌骨架 + 多贴图）。

NIKKE：每个角色有 main/aim/cover 三个姿势（各自独立 skel+atlas+贴图），
options["pose"] 指定导出哪个姿势；运行时按该姿势 skel 的版本（4.0/4.1）选择。
"""

from __future__ import annotations

import base64
import json
import re
import shutil
from pathlib import Path

from core.backgrounds import resolve_background_file
from core.registry import ExporterPlugin
from core.wallpaper import (
    WALLPAPER_LAYOUT,
    bg_css_for_skin,
    export_defaults,
    project_dir_name,
    project_json,
    render_template,
    spine_runtime,
    wallpaper_title,
)


class WallpaperSpineExporter(ExporterPlugin):
    id = "wallpaper_spine"
    name = "Spine 壁纸导出"

    def export(self, skin: dict, options: dict, out_dir: str) -> str:
        out = Path(out_dir)
        proj = out / project_dir_name(skin["ship"], skin["name"])
        assets = proj / "assets"
        assets.mkdir(parents=True, exist_ok=True)

        asset = skin.get("asset") or {}
        poses = asset.get("poses") or {}
        pose = options.get("pose") or "main"
        entry = poses.get(pose) or poses.get("main") or (poses[sorted(poses)[0]] if poses else None)
        if not entry:
            raise ValueError("该皮肤无可用姿势资源，请先下载")
        src_dir = Path(options["root"]) / "resources" / asset["dir"]

        version = str(entry.get("version") or "4.1")
        if not version.startswith("4."):
            version = "4.1"
        runtime_name = f"spine-webgl-{version}.js"
        shutil.copy2(spine_runtime(version), proj / runtime_name)
        shutil.copy2(WALLPAPER_LAYOUT, proj / "wallpaper-layout.js")

        # 姿势条目内 skel/atlas 是带姿势前缀的相对路径（如 main/c010_01_00.skel），
        # 贴图页名相对 atlas 所在目录解析。
        skel_rel = entry["skel"]
        atlas_rel = entry["atlas"]
        pose_dir = Path(skel_rel).parent
        skel = (src_dir / skel_rel).read_bytes()
        atlas_text = (src_dir / atlas_rel).read_text(encoding="utf-8")
        pages = re.findall(r"^([^\r\n]+\.png)\s*$", atlas_text, re.M)
        textures = []
        for page in pages:
            page = page.strip().lstrip("\ufeff")
            shutil.copy2(src_dir / pose_dir / page, assets / page)
            textures.append({"page": page, "file": "assets/" + page})
        layers = [{
            "name": Path(skel_rel).name.replace(".skel", ""),
            "skelData": base64.b64encode(skel).decode("ascii"),
            "atlasText": atlas_text,
            "textures": textures,
        }]

        # 背景图导出：官方(background) / 扩图导入(custom) / 临时超分(preview) 三处统一解析
        bg_image_opt = options.get("bgImage")
        bg_img_css_ref = None
        if options.get("bg") == "image" and bg_image_opt:
            bg_file = resolve_background_file(options["root"], bg_image_opt)
            if bg_file is not None:
                shutil.copy2(bg_file, assets / bg_file.name)
                bg_img_css_ref = f"assets/{bg_file.name}"

        title = wallpaper_title(skin["ship"], skin["name"])
        html = render_template(
            "wallpaper_spine.html",
            LAYERS_JSON=json.dumps(layers, ensure_ascii=False),
            SPINE_RUNTIME=runtime_name,
            TITLE=title,
            BG_CSS=bg_css_for_skin(
                skin,
                options.get("root"),
                options.get("bg", "monet"),
                options.get("bgColor"),
                bg_image=bg_img_css_ref,
                bg_scale=options.get("bgScale", 100),
                bg_offset_x=options.get("bgOffsetX", 0),
                bg_offset_y=options.get("bgOffsetY", 0),
            ),
            **export_defaults(options),
        )
        (proj / "index.html").write_text(html, encoding="utf-8")
        (proj / "project.json").write_text(
            json.dumps(
                project_json(
                    title,
                    scale=options.get("scale", 100),
                    offset_x=options.get("offsetX", 0),
                    offset_y=options.get("offsetY", 0),
                    alignment=int(options.get("alignment", 0) or 0),
                    interaction=bool(options.get("interaction", True)),
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(proj)
