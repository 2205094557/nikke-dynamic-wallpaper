# AGENTS.md — NIKKE 立绘壁纸工坊（nikke-dynamic-wallpaper）

> 本文件会被 Codex / Claude Code / Cursor 等 agent 在仓库内工作时自动加载。
> 本仓库由 browndust2-wallpaper（碧蓝 → 棕2 迁移产物）改造而来：保留插件化架构与
> WE 导出/打包管线，游戏专属层（CDN 协议 / UnityPy 解包 / 语音 / 互动）全部移除，
> 换成 nikke-db 静态站直下 + Spine 双运行时。通用打包铁律见 pyinstaller-packaging / we-common。

## 架构一句话

`backend_server.py`（stdlib HTTP 后端，8766 开发 / 8770 打包）+ `plugins/sources/nikke_db.py`
（nikke-db Cloudflare Pages 静态站下载，无解包环节）+ `core/*`（registry/metadata/library/
palette/wallpaper/we_integration）+ `plugins/exporters/wallpaper_spine.py`（动态壁纸导出）+ Vue3 前端。

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

## 自定义背景 / 扩图合成工作流（关键）

用户可导入自己的背景（含外部扩图成果），与人物合成后导出 WE 壁纸。目录分工：

| 目录 | 作用 | 生命周期 |
|---|---|---|
| `resources/background/` | 官方解包场景图（339 png + 1 readme） | 只读素材 |
| `resources/output/` | **导出目录**：`导出扩图` 把当前背景复制进来（待扩图） | 中转，可自行清理 |
| `resources/input/` | **导入目录**：用户把扩图成品放这里，`导入扩图` **只扫这个文件夹** | 中转，可自行清理 |
| `resources/custom/` | 自定义背景库：`导入扩图` 的成果落盘于此 | 持久，参与预览/超分/导出 |
| `resources/preview/` | 超分产物临时缓存（`_preview.png`） | 退出即清理，母图持久可重跑 |

- 流程：导出到 output → 外部工具扩图 → 成品放进 input → 点「导入扩图」。**导出不自动弹文件夹**
  （早期版本每次导出都 `openOutpaintDir`，用户明确要求去掉）；弹文件夹只由「📁 output / 📁 input」
  两个按钮触发
- **路径解析统一走 `core/backgrounds.py::resolve_background_file()`**：custom → background → output
  → preview（input 只是导入暂存区，不参与解析）。超分与动态/静态导出器全部用它，别再各自拼
  `resources/xxx`（早期导出器只查 background+preview，扩图背景导出会丢图）
- `background_dirs(root)` 返回 **`BackgroundDirs` NamedTuple**（official/custom/output/input/preview），
  一律**按字段名访问**。历史教训：曾是裸元组，3/4 元组按位置解包错位过一次（outpaint 被当成
  preview，超分产物永远解析不到）——不要再改回位置解包
- **自定义优先 = 同名遮罩**：导入与官方同名的图会覆盖官方（列表去重只留 custom 那条，卡片带"自定义"
  角标）。还原官方：卡片右上 ✕ 二次确认删除，或删 `resources/custom/` 下文件
- **缩略图**：自定义背景用独立后缀 `thumbnails/background/<stem>__custom.webp`，与官方同名图互不覆盖；
  `get_available_backgrounds` 对缺失缩略图懒生成（官方/自定义都自愈）
- **导入按内容 sha1 比对**：已导入的跳过（幂等）；与同名官方内容一致的（"把没扩图的原始导出误丢进
  input"）记为 `unchanged` 跳过，避免凭空多出一层遮罩
- **非 png 自动转 png**：超分引擎只吃 png，jpg/webp/bmp 导入时转存 png（先写 preview 临时文件再比对
  替换，保证重复导入不重写）
- 接口：`GET /api/backgrounds`（含 `categories` 的 custom 分类、`customCount`、`outputDir`、`inputDir`）、
  `POST /api/backgrounds/{export-outpaint,import-outpaint,delete-custom,upscale}`、
  `POST /api/open/{output-dir,input-dir,custom-dir,background-dir}`。前端入口在 GalleryView
  「外观 → 扩图合成」条（导出扩图 / 导入扩图 / 📁 output / 📁 input）与背景选择弹窗工具栏
- **`resources/outpaint/` 是历史目录名**，已拆成 output（导出）+ input（导入）。若在老版本升级后看到它，
  按内容判定归位：与同名官方背景逐字节一致 → output/，否则 → input/（它里面的成品图通常已在 custom/，
  迁到 input/ 后再导入会被识别为"已导入过"而跳过，不会重复）
- **超分产物校验不能用固定字节数阈值**：`core/upscaler.py::output_is_valid()` 按
  「存在 + 非空 + 可解码」判定。小尺寸背景正常输出可能只有几十 KB，用 `>100000` 会被误判为失败
- 端到端验收已并入 `tools/verify_nikke.py` 第 4 段（导出→模拟扩图→成品进 input→导入→超分→合成导出
  →删除），并含"output 里的图不会被导入"的反证；该脚本结束时只删本次产生的文件，不污染用户已有导出；
  `--clean` 额外删除验收下载的测试角色

## 打包铁律（继承 + 本项目要点）

1. 前端 API 地址永不硬编码：`frontend/src/bridge/index.js` 走
   `import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8766'`；打包走
   `python scripts/build_pack.py`（强制 `vite build --mode packaged` → .env.packaged 8770
   → 校验产物无 8766 → PyInstaller → 产物自检，一步到位）。**裸 `npm run build` 会把 8766
   打进 `frontend/dist`，桌面版就会连开发后端**；临时自检可用
   `grep -ro "127.0.0.1:87[0-9][0-9]" frontend/dist/`（只应出现 8770）
2. **启动方式**：仓库只有一个源码版启动器 `start.bat`（→ `scripts/start_dev.py`：后端 8766 +
   Vite 5173 + 桌面窗口）。该 .bat 必须存为 **UTF-8 无 BOM + CRLF**，且首行 `chcp 65001`——
   GBK 正文配 65001（或 LF 换行）会让 cmd 按 UTF-8 读 GBK 字节，报
   `'器' 不是内部或外部命令` 之类的错并启动失败（已踩坑，两个旧 .bat 都栽在这）
3. 端口：开发 8766 + Vite 5173；打包 8770 + 静态 5174；`app_pack.py` 启动自己的后端
4. frozen 不能起子进程：tools/* 一律 `run_tool()` 进程内加载（backend_server.py）
5. 静态服务器 `unquote` URL + 目录穿越防护（app_pack.py Handler）
6. spec：`nikke.spec`（name nikke-dynamic-wallpaper；hiddenimports 含 plugins.sources.nikke_db，
   无 UnityPy/voice/extractors、无静态壁纸导出器）；产物自检见 scripts/build_pack.py
7. 发布前必跑：`python tools/verify_nikke.py --clean`（起独立后端 8799 → 下载 4.0/4.1 各一角色
   → 校验提取产物与版本 → 导出动态壁纸并检查 project.json/运行时版本 → 扩图工作流全链路
   → 清理本次产物；`--clean` 额外删除验收下载的角色）
8. **两个前端源的 localStorage 不互通**：开发窗口加载 5173、打包窗口加载 5174，收藏等
   localStorage 按 host:port 隔离 → 换启动方式会"看不到收藏"（数据没丢，只是另一个源）。
   排查/恢复见 `%APPDATA%\nikke-dynamic-wallpaper\webview\EBWebView\Default\Local Storage\leveldb`
   （键 `nk_wallpaper_skin_favs`，值为 UTF-16LE 的 `ship|bundle|name` 数组）

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
| 双击 .bat 报 `'器' 不是内部或外部命令` 后秒退 | .bat 是 GBK 正文 + `chcp 65001`（或 LF 换行），须 UTF-8 无 BOM + CRLF |
| 换个启动方式后收藏/设置全没了 | localStorage 按端口隔离（5173 ≠ 5174），数据没丢，见打包铁律 8 |
| 打包版连上开发后端 | 前端构建没用 `--mode packaged`（产物含 8766） |
| 导入的扩图背景超分/导出报"母图不存在" | 解析漏了 custom/output（统一用 resolve_background_file） |
| 超分小图报"输出异常" | 用了固定字节数阈值，改用 `output_is_valid()` |
| 自定义背景显示的还是官方缩略图 | 缩略图未用 `__custom` 后缀，与官方同名图互相覆盖 |
| 重启 WE 后壁纸消失 | 应用副本目录名含中文（必须 ASCII + marker 身份） |
