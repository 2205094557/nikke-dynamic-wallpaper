# AGENTS.md — NIKKE 立绘壁纸工坊（nikke-dynamic-wallpaper）

> 本文件会被 Codex / Claude Code / Cursor 等 agent 在仓库内工作时自动加载。
> 本仓库由 browndust2-wallpaper（碧蓝 → 棕2 迁移产物）改造而来：保留插件化架构与
> WE 导出/打包管线，游戏专属层（CDN 协议 / UnityPy 解包 / 语音 / 互动）全部移除，
> 换成 nikke-db 静态站直下 + Spine 双运行时。通用打包铁律见 pyinstaller-packaging / we-common。

## 架构一句话

`backend_server.py`（stdlib HTTP 后端，8766 开发 / 8770 打包）+ `plugins/sources/nikke_db.py`
（nikke-db Cloudflare Pages 静态站下载，无解包环节）+ `core/*`（registry/metadata/library/
palette/wallpaper/we_integration）+ `plugins/exporters/`（动态/静态壁纸导出）+ Vue3 前端。

## 资源模型（nikke-db 静态站）

- 角色资产 URL：`https://nikke-db-legacy.pages.dev/l2d/<id>/<pose>/<file>`
  - main 姿势在角色目录根：`<base>_00.skel` / `<base>_00.atlas`；aim/cover 在子目录：
    `<id>_aim_00.*` / `<id>_cover_00.*`（主文件名 = id，姿势名 + `_00`）
  - **`f` 字段**：清单(l2d.json)里特殊角色（事件演出等）的 `f` 是主文件名前缀，
    有 f 时主文件 = `<f>.skel`（不带 `_00`），aim/cover 不存在
- **404 伪装**：Cloudflare Pages 对缺失路径返回 200 + HTML 错误页（24KB）——
  "文件是否存在"必须按内容判定（skel 含版本号 / atlas 为文本 / png 魔数），不能只看状态码
- **atlas BOM**：页面贴图名可能带 UTF-8 BOM（`\ufeff`），下载器/预览/导出三处都要剥，
  否则拼 URL 404
- 贴图名从 atlas 文本第一列 `.png` 行解析（区域名顶格但不以 .png 结尾，不会误收）；
  姿势子目录下贴图相对 atlas 所在目录解析（预览 loadLayer 的 `poseDir`）
- 头像：`images/sprite/si_<id>_00_s.png`（PNG 内容，前端拼 `avatars/<f>.jpg` 需存 .jpg 后缀）

## Spine 双运行时（关键）

- NIKKE 骨骼版本不统一（实测 main 4.0.47 / 4.1.20 混用）：**4.1 运行时读不了部分 4.0 skel**
  （会抛 "Region not found in atlas"），必须按版本选运行时
- skel 头部第 9 字节起是 null 结尾版本串：`re.search(rb"\d+\.\d+\.\d+", head[:64])`
  → "4.0"/"4.1"（`build_local_index.py` 记录到 local_skins.json 每个姿势的 `version`）
- 后端导出：`core/wallpaper.py::spine_runtime(version)` 按 "4.0"/"4.1" 选模板运行时文件；
  导出器把 `spine-webgl-{版本}.js` 复制进壁纸项目，模板 `<script src="{{SPINE_RUNTIME}}">`
- 前端预览：`SpinePreview.vue::ensureRuntime(version)` 动态注入 `/vendor/spine-webgl-{v}.js`，
  同一时刻只保留一个版本（切换前删旧 script + 清 window.spine）。
  **版本判断必须 `startsWith('4.0')`**——`split('.')[0]` 得到 '4'，与 '4.0' 比较恒 false，
  会把所有 4.0 皮肤当成 4.1 加载（已踩坑）
- index.html 不再静态引入运行时（由组件按皮肤版本加载）

## 预乘 alpha（预览与模板必须一致）

- NIKKE atlas 页头 `pma:true`（预乘贴图）：上传原样直传
  （`UNPACK_PREMULTIPLY_ALPHA_WEBGL=false`）+ `drawSkeleton(skeleton, true)` 预乘混合
- `SpinePreview.vue::NIKKE_PREMULTIPLY_UPLOAD` 与 `templates/wallpaper_spine.html::
  NIKKE_PREMULTIPLY_UPLOAD` 恒为 false（BD2 是直通 alpha 为 true，别照搬旧值）
- 验证：浅色背景下角色不发白/不发黑；半透明纱裙无灰边

## 打包铁律（继承 + 本项目要点）

1. 前端 API 地址永不硬编码：`frontend/src/bridge/index.js` 走
   `import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8766'`；打包必须
   `vite build --mode packaged`（.env.packaged → 8770），`build_pack.py` 校验产物无 8766
2. 端口：开发 8766 + Vite 5173；打包 8770 + 静态 5174；`app_pack.py` 启动自己的后端
3. frozen 不能起子进程：tools/* 一律 `run_tool()` 进程内加载（backend_server.py）
4. 静态服务器 `unquote` URL + 目录穿越防护（app_pack.py Handler）
5. spec：`nikke.spec`（name nikke-dynamic-wallpaper；hiddenimports 含 plugins.sources.nikke_db，
   无 UnityPy/voice/extractors）；产物自检见 build_pack.py required 字典
6. 发布前必跑：`python tools/verify_nikke.py --clean`（起独立后端 8799 → 下载 4.0/4.1 各一角色
   → 校验提取产物与版本 → 导出动态/静态壁纸 → 检查 project.json/运行时版本 → 清测试数据）

## WE 集成（we_integration.py）

- 一键应用副本目录名 ASCII 化（`nk2d_<uuid8>`），标记文件 `.nk-marker` 内容 = `{ship}_{name}`
  身份，应用前清理同身份旧副本；中文路径走 openWallpaper 会乱码（铁律）
- project.json 属性：scalectrl/offsetx/offsety/alignment combo（`{label,value}` + 字符串 value +
  `editable:true`），无语音/开场/互动属性（NIKKE 无这些功能，导出器不生成）
- 壁纸模板 `wallpaper_spine.html` 的 `wallpaperPropertyListener`：首推无条件跳过版式

## 元数据（tools/fetch_nikke_metadata.py）

- 清单：nikke-db-vue 仓库 `src/utils/json/l2d.json`（id/英文名/cn 中文名/f 字段）；
  可下载集合 = GitHub API `l2d/` 目录列表（per_page=1000 两页，GitHub 会重复返回同批目录，
  必须 setdefault 去重）；网络失败回退本地缓存
- 同名去重：l2d.json 存在多个 id 同名（量产 Rapi 的 c010/c989/c990/c994 都叫"拉毗"），
  ship 显示名后加 ` (id)` 后缀，否则前端按名字挂接皮肤会串组
- 头像在元数据更新时下载（si_<base>_00_s.png → avatars/<base>.jpg）；文件名不带扩展名
  （前端拼 `.jpg`）
- 拼音：`core/pinyin_index.py`（fetch_nikke_metadata 与 build_local_index 共用）

## 已知坑速查

| 现象 | 原因 |
|---|---|
| 预览黑屏/卡住，dbg 停跳 | 检查是否 HMR 残留（运行时脚本与组件状态错位）——整页重载验证 |
| 4.0 皮肤报 "Region not found in atlas" | 运行时选成了 4.1（ensureRuntime 版本判断写错） |
| 贴图 404 / texture load failed | atlas 页面名带 BOM 未剥，或姿势子目录前缀漏拼 |
| 下载器把 HTML 错误页当资源 | 缺失文件返回 200，需按内容魔数校验 |
| 角色名串组 | 同名 ship 未加 id 后缀（重建元数据） |
| 打包版连上开发后端 | 前端构建没用 --mode packaged（产物含 8766） |
| 重启 WE 后壁纸消失 | 应用副本目录名含中文（必须 ASCII + marker 身份） |
