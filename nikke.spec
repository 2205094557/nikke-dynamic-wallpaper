# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：onedir，包含代码 + 模板 + 元数据 + 头像 + 前端 dist。"""
from PyInstaller.utils.hooks import collect_all

import os


def _walk_files(src, dest_prefix, skip=()):
    out = []
    for root, _dirs, files in os.walk(src):
        for f in files:
            if f in skip:
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(root, src)
            out.append((full, os.path.join(dest_prefix, rel)))
    return out


datas = [
    ("templates", "templates"),
    ("resources/avatars", "resources/avatars"),
    ("frontend/dist", "frontend/dist"),
    ("tools", "tools"),
    ("core", "core"),
    # plugins 目录必须作为文件打包：注册表按目录扫描发现插件
    ("plugins", "plugins"),
]
# 元数据：排除 local_skins.json（本地下载索引，打包版从空状态开始）
datas += _walk_files("resources/metadata", "resources/metadata", skip={"local_skins.json"})

p_datas, p_bins, p_hidden = collect_all("pypinyin")
datas += p_datas
binaries = p_bins

hiddenimports = (
    [
        "core.registry",
        "core.metadata",
        "core.library",
        "core.palette",
        "core.we_integration",
        "core.events",
        "core.wallpaper",
        "plugins.sources.nikke_db",
        "plugins.sources.local",
        "plugins.exporters.wallpaper_spine",
        "requests",
        "PIL",
    ]
    + p_hidden
)

_icon = os.path.join(SPECPATH, "resources", "icon.ico")
icon = _icon if os.path.exists(_icon) else None

a = Analysis(
    ["app_pack.py"],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="nikke-dynamic-wallpaper",
    icon=icon,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="nikke-dynamic-wallpaper",
)
