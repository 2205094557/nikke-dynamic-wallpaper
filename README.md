# NIKKE 立绘壁纸工坊 (nikke-dynamic-wallpaper)

<p align="center">
  <img src="resources/icon.ico" width="96" height="96" alt="NIKKE Wallpaper Icon" />
</p>

<p align="center">
  <strong>《胜利女神：妮姬》高画质动态立绘壁纸工具</strong><br>
  官方 Spine 4.0/4.1 双运行时自动适配 · 339 张官方场景背景与智能剧情推荐 · 外部扩图与自定义背景合成<br>
  NCNN GPU 本地 AI 超分放大 · 点击互动与情绪表情轮询状态机 · Wallpaper Engine 一键导出与无缝联动
</p>

---

## 🌟 项目亮点

- 🎯 **纯正全角色图鉴**：已剔除无脸 NPC / 杂兵 / 剧情 Boss，纯粹收录 **237 位正统可玩妮姬与联动角色（423 套皮肤）**，全量补齐官方中文译名，支持汉字全拼与首字母模糊检索。
- ⚡ **Spine 4.0 / 4.1 双运行时自动切换**：解决 NIKKE 骨骼版本不统一导致的 "Region not found in atlas" 报错，底层按骨骼二进制头部自动按需注入对应 runtime。
- 🎭 **大厅 / 瞄准 / 封面三姿势**：无解包环节，直连静态资产库，大厅待机、瞄准射击态、掩体封面态任意即时切换。
- 🌄 **339 张官方解包场景图库**：
  - 全量赋予官方剧情中文命名（如 *皇冠城堡 · 正门*、*指挥官办公室*、*金币狂潮 · 豪华大厅*、*灰姑娘的纯澈苍穹* 等）；
  - 角色剧情智能关联推荐（选择妮姬自动推荐对应战役据点/活动场景）；
  - 支持按分类标签（皇冠王国、方舟都会、前哨基地、伊甸园、海滩度假村、雪原温泉、金币狂潮、荒原废墟）检索。
- 🖼️ **自定义背景与扩图工作流**：
  - 导出待扩图背景至 `output/`；
  - 外部工具（Photoshop / 外部 AI 等）完成 16:9 扩展后放入 `input/`；
  - 软件内一键导入至 `custom/` 库并自动生成轻量缩略图，即刻参与预览、超分与壁纸导出。
- 🚀 **内置 NCNN GPU 本地 AI 超分系统**：
  - 集成 **Waifu2x（2025新版架构）**、**Real-CUGAN（二次元专属）**、**Real-ESRGAN** 三套 Vulkan 硬件加速引擎；
  - 支持 2x 放大 / 4x 极清输出，产物持久化缓存复用；
  - 支持高级参数调优：降噪等级（Denoise）、TTA 8方向多角度增强采样、4x $\rightarrow$ 2x 超采样方案；
  - 具备母图智能溯源算法，彻底杜绝多重放大带来的画质劣化。
- 🖱️ **精致版式调节与 1:1 绝对锁合拖拽**：
  - 舞台右上角极简毛玻璃悬浮胶囊控制条（**画面 / 人物 / 背景**）；
  - **画面模式**：人物与背景如同烙印在同一块画板上，1:1 绝对物理像素锁合平移与等比缩放，彻底消除相对位移漂移；
  - **人物 / 背景独立模式**：单独调节构图与取景位置。
- 💫 **点击互动与情绪表情轮询系统**：
  - **默认待机**：角色常驻循环播放专属 `idle` 呼吸待机；
  - **首击触发**：轻点角色立即播放全身专属 `action` 互动大动作，播放完毕平滑切回待机；
  - **持续互动**：再次点击从表情池中随机抽取表情（`shy` 害羞、`happy` 开心、`delight` 喜悦、`sad` 难过、`good` 赞许、`no` 摇头、`surprise` 惊讶、`angry` 生气、`cry` 哭泣等）并持久保持；
  - **排除杂项轨**：自动过滤 `talk` 张嘴动作与 `bg_` 背景道具轨；
  - **循环闭环**：所有表情播放一轮后重置，下一次点击重回 `action` 大动作。
- 🖥️ **Wallpaper Engine 深度联动**：
  - 一键导出原生标准壁纸项目并自动激活；
  - 自动将所选的官方场景或超分背景打包进工程；
  - 壁纸侧边栏包含 **【点击互动】** 复选框，可随时开启互动或锁定安静待机；
  - 附带缩放、水平/垂直偏移、对齐方式等原生调节滑块。

---

## 🗂️ 目录结构

```
nikke-dynamic-wallpaper/
├── start.bat                   # 源码版一键启动入口（UTF-8 + CRLF）
├── backend_server.py           # 本地 Python 后端 API（开发 8766 / 打包 8770）
├── web_main.py / app_pack.py   # pywebview 桌面窗口入口
├── core/                       # 核心业务逻辑
│   ├── backgrounds.py          # 场景背景分类、官方中文名对照与智能推荐
│   ├── upscaler.py             # NCNN GPU 本地 AI 超分放大管线
│   ├── wallpaper.py            # Wallpaper Engine 项目配置与 CSS 注入
│   ├── we_integration.py       # Wallpaper Engine 命令行联动与应用
│   ├── metadata.py             # 角色与皮肤元数据管理
│   ├── palette.py              # 取色调色板与备用 CSS 生成
│   └── pinyin_index.py         # 中文全拼与首字母检索索引
├── plugins/                    # 插件层
│   ├── sources/nikke_db.py     # nikke-db 静态站资产下载源（带内容校验）
│   └── exporters/              # wallpaper_spine 动态壁纸导出器
├── tools/                      # 工具与超分依赖
│   ├── waifu2x-ncnn-vulkan/    # Waifu2x 2025 GPU Vulkan 引擎
│   ├── realcugan-ncnn-vulkan/  # Real-CUGAN GPU Vulkan 引擎
│   ├── realesrgan-ncnn-vulkan/ # Real-ESRGAN GPU Vulkan 引擎
│   ├── fetch_nikke_metadata.py # 元数据构建与清洗脚本
│   └── verify_nikke.py         # 发布前自动化全链路验收脚本
├── templates/                  # 壁纸模板（index.html、spine40/41运行时、layout）
├── resources/                  # 运行资源目录
│   ├── metadata/               # 237 位妮姬元数据与拼音索引
│   ├── avatars/                # 角色官方头像
│   ├── background/             # 339 张官方解包场景图（用户放置）
│   ├── custom/                 # 自定义背景库（扩图导入产物）
│   ├── output/                 # 导出待扩图背景目录
│   ├── input/                  # 外部扩图成品放入目录
│   └── preview/                # 超分高清背景持久化缓存
└── frontend/                   # Vue 3 + Vite + Naive UI 现代化界面
```

---

## 🚀 快速开始

### 1. 环境准备
- **Python 3.10+**
- **Node.js 18+** 与 npm / pnpm

### 2. 安装依赖

```bash
# 1. 安装后端依赖
pip install -r requirements.txt

# 2. 安装前端依赖
cd frontend
npm install
cd ..
```

### 3. 一键启动
双击运行根目录下的 **`start.bat`** 即可自动拉起：
- 后端服务：`http://127.0.0.1:8766`
- 前端开发服务：`http://127.0.0.1:5173`
- 专属桌面客户端窗口（自动居中与记忆尺寸）

---

## 🛠️ 打包发布

本项目支持通过 PyInstaller 构建免安装便携桌面版：

```bash
# 完整自动化打包（强制 packaged 模式构建前端 + 产物自检）
python scripts/build_pack.py
```

打包产物位于 `dist/nikke-dynamic-wallpaper/`，内部使用独立隔离端口（后端 8770 + 静态前端 5174），解压即用。

---

## 📖 常见问题说明

1. **角色资产首次下载速度慢？**
   - 资产直连自 Cloudflare Pages 静态节点，可在软件「设置 → 网络」中填入本地 HTTP 代理端口（如 `http://127.0.0.1:7890`）进行加速。
2. **手机端 Wallpaper Engine 如何使用？**
   - 手机端 Wallpaper Engine 由于功耗限制不内置浏览器内核，因此对 Web 类型壁纸不支持直接传输。可在电脑端右键点击导出的壁纸，使用官方的转码功能将其转为高清无缝循环视频发送至手机。
3. **AI 超分是否需要联网或 API Key？**
   - 完全不需要。超分引擎内置于 `tools/` 目录，直接调用本地独立显卡（NVIDIA / AMD / Intel 均支持 Vulkan）进行硬件推理，不耗费任何在线 Token。

---

## ⚖️ 免责声明与版权

- 本项目使用的《胜利女神：妮姬》游戏相关素材、立绘、骨骼、场景及音频版权均归属 **SHIFT UP** 及发行商 **Level Infinite**。
- 本工具为开源非商业项目，仅供二次元爱好者与开发者学习交流使用，严禁用于任何商业牟利行为。
