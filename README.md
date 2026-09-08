# NIKKE 立绘壁纸工坊

《胜利女神：NIKKE》立绘壁纸工具。从 [nikke-db](https://nikke-db.pages.dev/) 资源站下载 **Spine 动态立绘**（大厅 / 瞄准 / 封面三姿势，4.0 / 4.1 双运行时自动匹配），在图鉴式 Web 界面中预览，导出为 Wallpaper Engine 壁纸项目并一键应用到桌面。

由 [browndust2-wallpaper](https://github.com/2205094557/browndust2-wallpaper)（棕色尘埃2 壁纸工具，源自 azurlane-dynamic-wallpaper）迁移改造而来，保留其插件化架构，游戏专属层全部替换。

## 功能

- **资源下载**：从 nikke-db 静态站按需下载角色 Spine 资产（`skel / atlas / png`，无解包环节），断点续传 + 内容校验（站点对缺失文件返回 200 + HTML 错误页，按内容魔数判定）
- **三姿势**：main（大厅动画）/ aim（瞄准）/ cover（封面），预览与导出均可切换
- **双运行时**：NIKKE 骨骼版本不统一（实测 4.0.47 / 4.1.20 混用），索引记录每姿势版本，预览与导出按版本自动选 spine-webgl 4.0 / 4.1
- **图鉴预览**：518+ 角色 / 725+ 皮肤，中文名 / 拼音检索 / 收藏 / 批量下载，取色背景（自动 / 纯色 / 莫奈 / 毛玻璃 / 星空）
- **壁纸导出**：动态壁纸（Spine 动画循环）+ 静态壁纸（预览截图），Wallpaper Engine 属性（缩放 / 偏移 / 对齐）原生格式，一键应用
- **元数据自动更新**：拉取 nikke-db 角色清单（含中文名 / 头像），自动收录新角色

## 快速开始（开发模式）

```bash
# 后端依赖（pywebview / requests / Pillow / pypinyin）
pip install -r requirements.txt

# 前端依赖
cd frontend && npm install && cd ..

# 一键启动：后端 8766 + Vite 5173 + 桌面窗口
python scripts/start_dev.py
# 或只启动后端供浏览器访问：
python backend_server.py 8766   # 然后打开 http://127.0.0.1:5173
```

首次使用在「设置 → 数据更新」点**重建元数据**（同步角色清单 / 中文名 / 头像），然后在图鉴页下载角色即可预览。

> 开发机预览素材走 Vite `/@fs/`，路径在 `frontend/.env.development` 的 `VITE_DEV_RESOURCES` 配置，换机器需修改。

## 打包发布

```bash
python scripts/build_pack.py            # 构建 + 静态自检（产物 dist/nikke-dynamic-wallpaper/）
python tools/verify_nikke.py --clean    # 发布前全链路验收（下载→校验→导出→检查），通过后清空测试数据
```

打包版入口 `app_pack.py`：内置后端（8770）+ 静态前端（5174）+ pywebview 窗口。

## 目录结构

```
nikke-dynamic-wallpaper/
├── backend_server.py        # 本地后端 API（8766 开发 / 8770 打包）
├── app_pack.py / web_main.py# 打包版 / 开发版桌面入口（pywebview）
├── core/                    # registry / metadata / library / palette / wallpaper / we_integration ...
├── plugins/
│   ├── sources/nikke_db.py  # ★ nikke-db 静态站下载源（角色资产 + 头像）
│   └── exporters/           # wallpaper_spine（动态）/ wallpaper_static（静态）
├── tools/
│   ├── fetch_nikke_metadata.py  # 元数据构建（l2d.json 清单 + 目录列表 + 头像 + 拼音）
│   ├── build_local_index.py     # 本地索引（姿势 + spine 版本检测）
│   └── verify_nikke.py          # 发布前验收
├── templates/               # WE 壁纸模板 + spine40/41 运行时 + wallpaper-layout.js
└── frontend/                # Vue 3 + Vite + Naive UI
```

## 数据源说明

- 角色资产：`https://nikke-db-legacy.pages.dev/l2d/<id>/...`（Cloudflare Pages 静态托管，文件源头在 GitHub 仓库 `Nikke-db/Nikke-db.github.io`）
- 角色清单：nikke-db-vue 仓库 `src/utils/json/l2d.json`（id + 英文名 + 中文名 + `f` 文件名前缀字段）
- 头像：`images/sprite/si_<id>_00_s.png`
- 资源版权归 Shift Up / Level Infinite，仅供个人学习交流使用
