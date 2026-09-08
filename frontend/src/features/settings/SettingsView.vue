<template>
  <div class="page-wrap">
    <div class="page-header">
      <h1>设置</h1>
      <div class="page-nav">
        <button
          class="wc-btn page-nav-btn"
          :class="{ active: route.path === '/gallery' }"
          @click="router.push('/gallery')"
        >
          ⚓ 角色图鉴
        </button>
        <button
          class="wc-btn page-nav-btn"
          :class="{ active: route.path === '/settings' }"
          @click="router.push('/settings')"
        >
          ⚙ 设置
        </button>
      </div>
    </div>

    <div class="settings-grid">
      <n-card title="下载目录" size="small" class="wc-card">
        <p class="dim">角色 Spine 资源保存在软件资源目录（下载即就绪，无需解包）。</p>
        <div class="row">
          <n-button size="small" secondary @click="openDir('download')">打开下载目录</n-button>
          <n-button size="small" secondary @click="openDir('extracted')">打开提取目录</n-button>
        </div>
      </n-card>

      <n-card title="壁纸导出" size="small" class="wc-card">
        <div class="row">
          <n-button size="small" type="primary" :loading="openingWe" @click="openWe">
            打开壁纸文件夹
          </n-button>
          <n-popconfirm @positive-click="cleanExports" positive-text="清理" negative-text="取消">
            <template #trigger>
              <n-button size="small" type="error" secondary :loading="cleaningExports">
                清理导出目录
              </n-button>
            </template>
            将删除 resources/wallpapers 与 resources/exports 下所有导出的壁纸项目与截图，确定吗？
          </n-popconfirm>
          <span class="dim">清理后需重新导出壁纸</span>
        </div>
      </n-card>

      <n-card title="网络" size="small" class="wc-card">
        <div class="field">
          <label>代理服务器</label>
          <n-input v-model:value="proxy" placeholder="http://127.0.0.1:7890（留空不使用）" />
        </div>
        <div class="field">
          <label>并发下载数</label>
          <n-slider v-model:value="concurrency" :min="1" :max="8" />
          <span class="dim">“下载全部 / 批量下载”时同时下载的皮肤数（单个下载不受影响）</span>
        </div>
      </n-card>

      <n-card title="外观主题" size="small" class="wc-card">
        <div class="field">
          <label>界面主题</label>
          <div class="theme-picker">
            <div
              v-for="t in themeOptions"
              :key="t.key"
              class="theme-opt"
              :class="{ active: themeKey === t.key }"
              @click="setTheme(t.key)"
            >
              <span class="theme-swatch" :class="'theme-swatch-' + t.key"></span>
              <span class="theme-name">{{ t.label }}</span>
              <span class="theme-check" :class="{ show: themeKey === t.key }">✓</span>
            </div>
          </div>
          <span class="dim">切换立即生效，选择会保存；少女漫画风含樱花粉、网点与花朵元素。</span>
        </div>
      </n-card>

      <n-card title="提示音" size="small" class="wc-card">
        <div class="field">
          <label>音色</label>
          <n-select v-model:value="soundTimbre" :options="soundOptions" size="small" />
        </div>
        <div class="field">
          <label>音量（{{ soundVolume }}%）</label>
          <n-slider v-model:value="soundVolume" :min="0" :max="100" :step="5" />
        </div>
        <div class="row">
          <n-button size="small" secondary @click="previewSound">▶ 试听</n-button>
          <span class="dim">下载完成时播放，音量 0 即静音</span>
        </div>
      </n-card>

      <n-card title="数据更新" size="small" class="wc-card">
        <p class="dim">
          数据源为 nikke-db 资源站（角色 Spine 资产与角色清单，含中文名/英文名/头像）。
          重建元数据会拉取最新角色清单与可下载目录，自动收录新角色与新皮肤。
        </p>
        <div class="row" style="margin-bottom: 6px">
          <n-button size="small" type="primary" :loading="updating" @click="updateData">
            重建元数据（同步角色清单 / 中文名 / 头像）
          </n-button>
        </div>
        <div v-if="updateResult" class="update-result">
          <div class="group-title">更新结果</div>
          <div v-for="(s, k) in updateResult.steps || {}" :key="k" class="update-line">
            {{ k }}：{{ s.ok ? '完成' : '失败' }}
          </div>
          <div v-if="updateResult.error" class="update-error">{{ updateResult.error }}</div>
        </div>
      </n-card>

      <n-card title="已下载资源" size="small" class="wc-card span-2">
        <div class="row" style="margin-bottom: 10px">
          <n-button size="small" type="primary" :loading="loading" @click="refresh">
            刷新列表
          </n-button>
          <n-input
            v-model:value="searchDl"
            placeholder="搜索角色 / 皮肤…"
            clearable
            size="small"
            style="width: 220px"
          >
            <template #prefix>🔍</template>
          </n-input>
          <n-button size="small" secondary @click="toggleAllSel">
            {{ allSelected ? '取消全选' : '全选' }}
          </n-button>
          <n-popconfirm
            :disabled="!selCount"
            @positive-click="delSelected"
            positive-text="删除所选"
            negative-text="取消"
          >
            <template #trigger>
              <n-button size="small" type="error" secondary :loading="deletingSel" :disabled="!selCount">
                {{ deletingSel ? `删除所选 ${delDone}/${delTotal}` : `删除所选 (${selCount})` }}
              </n-button>
            </template>
            将删除选中的 {{ selCount }} 个皮肤本地文件，确定吗？
          </n-popconfirm>
          <n-popconfirm @positive-click="clearAll" positive-text="全部删除" negative-text="取消">
            <template #trigger>
              <n-button size="small" type="error" secondary :loading="clearing">
                删除全部已下载
              </n-button>
            </template>
            将删除 extracted 目录中的所有已下载内容，且不可撤销，确定吗？
          </n-popconfirm>
          <span class="dim">
            共 {{ downloaded.length }} 个皮肤
            <span v-if="selCount"> · 已选 {{ selCount }}</span>
          </span>
        </div>
        <n-spin :show="loading">
          <div v-if="filteredDl.length" class="dl-list">
            <div
              v-for="s in filteredDl"
              :key="s.ship + s.bundle"
              class="dl-item"
              :class="{ selected: isSel(s) }"
              @click="toggleSel(s)"
            >
              <span class="dl-check" :class="{ on: isSel(s) }">✓</span>
              <span class="dl-name">{{ s.ship }} · {{ s.name }}</span>
              <span class="wc-pill" :class="pillClass(s.type)">{{ typeLabel(s.type) }}</span>
              <n-popconfirm @positive-click.stop="delOne(s)" positive-text="删除" negative-text="取消">
                <template #trigger>
                  <n-button size="tiny" quaternary type="error" @click.stop>删除</n-button>
                </template>
                删除 {{ s.ship }} · {{ s.name }} 的本地文件？
              </n-popconfirm>
            </div>
            <div v-if="downloaded.length && !filteredDl.length" class="dim" style="padding: 10px 0">
              无匹配结果
            </div>
          </div>
          <n-empty v-else description="暂无已下载皮肤" style="padding: 20px 0" />
        </n-spin>
      </n-card>

      <n-card title="关于" size="small" class="wc-card">
        <div class="about">
          <div class="about-head">
            <span class="about-logo">⚓</span>
            <div class="about-title">
              <div class="about-name">NIKKE 立绘壁纸工坊</div>
              <div class="about-version">v0.1.0</div>
            </div>
          </div>
          <p class="about-desc">
            从 nikke-db 资源站下载 <b>Spine 动态立绘</b>（大厅 / 瞄准 / 封面姿势，
            4.0/4.1 双运行时自动匹配），在图鉴式 Web 界面中预览，导出为 Wallpaper Engine
            壁纸项目，一键应用到桌面。
          </p>
          <div class="about-sec">功能特性</div>
          <ul class="about-list">
            <li>全角色 Spine 大厅动画按需下载（main / aim / cover 三姿势）</li>
            <li>图鉴式预览（取色 / 莫奈 / 毛玻璃 / 星空等背景）</li>
            <li>动态壁纸导出（Spine 动画循环）+ 静态壁纸导出（预览截图）</li>
            <li>导出 Wallpaper Engine 壁纸项目（project.json 原生属性 + 一键应用）</li>
          </ul>
          <div class="about-sec">技术栈</div>
          <p class="about-desc">
            桌面外壳 pywebview + WebView2 · 后端 Python 插件化（sources / exporters）·
            前端 Vue 3 + Vite + Naive UI · Spine 用 spine-webgl 4.0/4.1 WebGL 运行时 ·
            资源来自 nikke-db 静态站直下。
          </p>
          <div class="about-foot">Windows 10 / 11 · 资源仅供个人学习交流使用</div>
        </div>
      </n-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NCard, NInput, NSelect, NSlider, NButton, NSpin, NEmpty, NPopconfirm, useMessage } from 'naive-ui'
import { bridge } from '../../bridge'
import { themeKey, setTheme, THEMES } from '../../utils/theme'
import { TIMBRES, getSoundPrefs, playChime, setSoundPrefs, warmAudio } from '../../utils/sound'

const route = useRoute()
const router = useRouter()

const message = useMessage()
const themeOptions = THEMES
const proxy = ref('')
const concurrency = ref(parseInt(localStorage.getItem('nk_concurrency') || '4', 10) || 4)
const downloaded = ref([])
const loading = ref(false)
const clearing = ref(false)
const openingWe = ref(false)
const cleaningExports = ref(false)
const searchDl = ref('')
const selKeys = ref(new Set())
const deletingSel = ref(false)
const delDone = ref(0)
const delTotal = ref(0)
const updating = ref(false)
const updateResult = ref(null)
const soundOptions = TIMBRES.map((t) => ({ label: t.name, value: t.id }))
const soundTimbre = ref(getSoundPrefs().timbre)
const soundVolume = ref(getSoundPrefs().volume)

function typeLabel(t) {
  return t === 'spine' ? 'Spine' : '静态'
}

function pillClass(t) {
  return t === 'static' ? 'blue' : 'green'
}

watch([soundTimbre, soundVolume], () => {
  setSoundPrefs({ timbre: soundTimbre.value, volume: soundVolume.value })
})

watch(concurrency, (v) => {
  localStorage.setItem('nk_concurrency', String(v))
})

// 代理设置：读后端配置初始化，修改后防抖保存（立即生效于下一次下载）
let proxyTimer = null
watch(proxy, (v) => {
  clearTimeout(proxyTimer)
  proxyTimer = setTimeout(() => {
    bridge.setConfig({ proxy: v })
  }, 400)
})

async function loadConfig() {
  try {
    const res = await bridge.getConfig()
    if (res && res.ok && res.config) {
      proxy.value = res.config.proxy || ''
    }
  } catch (e) {
    /* 后端未启动时忽略，代理保持空 */
  }
}

function previewSound() {
  warmAudio()
  playChime()
}

const filteredDl = computed(() => {
  const kw = searchDl.value.trim().toLowerCase()
  if (!kw) return downloaded.value
  return downloaded.value.filter((s) => `${s.ship} ${s.name}`.toLowerCase().includes(kw))
})
const selCount = computed(() => selKeys.value.size)
const allSelected = computed(
  () => filteredDl.value.length > 0 && filteredDl.value.every((s) => selKeys.value.has(keyOf(s))),
)

function keyOf(s) {
  return `${s.ship}|${s.bundle}`
}

function isSel(s) {
  return selKeys.value.has(keyOf(s))
}

function toggleSel(s) {
  const k = keyOf(s)
  const set = new Set(selKeys.value)
  if (set.has(k)) set.delete(k)
  else set.add(k)
  selKeys.value = set
}

function toggleAllSel() {
  const set = new Set(selKeys.value)
  if (allSelected.value) {
    for (const s of filteredDl.value) set.delete(keyOf(s))
  } else {
    for (const s of filteredDl.value) set.add(keyOf(s))
  }
  selKeys.value = set
}

async function delSelected() {
  const targets = downloaded.value.filter((s) => selKeys.value.has(keyOf(s)))
  if (!targets.length) return
  deletingSel.value = true
  delDone.value = 0
  delTotal.value = targets.length
  let failed = 0
  // 批量接口：后端一次删完全部文件只重建一次索引（逐个调用是 N 次全量重建，很慢）。
  // 进度按已提交数量显示（批量接口原子完成，无逐个回调）。
  try {
    const items = targets.map((s) => ({ ship: s.ship, bundle: s.bundle, name: s.name }))
    const res = await bridge.deleteSkinsBatch(items)
    if (res && res.ok === false && res.failed_count != null) failed = res.failed_count
    else if (res && res.failed_count != null) failed = res.failed_count
    else if (res && res.ok === false) failed = targets.length
  } catch (e) {
    failed = targets.length
  }
  delDone.value = delTotal.value
  deletingSel.value = false
  selKeys.value = new Set()
  await refresh()
  message.success(
    failed
      ? `删除完成：${delTotal.value - failed} 成功，${failed} 失败`
      : `已删除 ${delTotal.value} 个皮肤`,
  )
}

async function refresh() {
  loading.value = true
  try {
    const res = await bridge.listDownloaded()
    downloaded.value = (res && res.skins) || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function openDir(kind) {
  const res = kind === 'download' ? await bridge.openDownloadDir() : await bridge.openExtractedDir()
  if (res && res.ok) message.success('已打开目录')
  else message.error((res && res.error) || '打开目录失败')
}

async function openWe() {
  openingWe.value = true
  try {
    const res = await bridge.openWallpapersDir()
    if (res && res.ok) message.success('已打开壁纸文件夹')
    else message.error((res && res.error) || '打开失败')
  } finally {
    openingWe.value = false
  }
}

async function cleanExports() {
  cleaningExports.value = true
  try {
    const res = await bridge.cleanExports()
    if (res && res.ok) message.success(`已清理 ${res.removed} 个导出文件/目录`)
    else message.error((res && res.error) || '清理失败')
  } finally {
    cleaningExports.value = false
  }
}

async function delOne(s) {
  const res = await bridge.deleteSkin(s.ship, s.bundle, s.name)
  if (res && res.ok) {
    message.success(`已删除 ${s.ship} · ${s.name}`)
    await refresh()
  } else {
    message.error((res && res.error) || '删除失败')
  }
}

async function clearAll() {
  clearing.value = true
  try {
    const res = await bridge.clearDownloads()
    if (res && res.ok) {
      message.success('已清空全部下载')
      await refresh()
    } else {
      message.error((res && res.error) || '清空失败')
    }
  } finally {
    clearing.value = false
  }
}

async function updateData() {
  updating.value = true
  updateResult.value = null
  try {
    const res = await bridge.updateMetadata()
    updateResult.value = res
    if (res && res.ok) {
      const failed = Object.values(res.steps || {}).filter((s) => !s.ok).length
      if (failed) message.warning(`元数据重建完成，${failed} 个步骤失败`)
      else message.success('元数据重建完成')
    } else {
      message.error((res && res.error) || '更新失败')
    }
  } catch (e) {
    message.error(`更新失败：${e.message}`)
  } finally {
    updating.value = false
  }
}

onMounted(() => {
  refresh()
  loadConfig()
})
onActivated(refresh)
onBeforeUnmount(() => {
  clearTimeout(proxyTimer)
})
</script>

<style scoped>
.page-wrap {
  padding: 26px 30px 40px;
  max-width: 960px;
  margin: 0 auto;
}

.page-header h1 {
  margin: 0;
  font-family: var(--font-serif);
  font-weight: 300;
  letter-spacing: 3px;
  font-size: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-nav {
  display: flex;
  gap: 8px;
}

.page-nav-btn {
  padding: 7px 16px;
  border-radius: 999px;
}

.page-nav-btn.active {
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(133, 205, 202, 0.14));
  border-color: rgba(74, 111, 165, 0.55);
  color: #3a5a88;
  box-shadow: 0 4px 16px rgba(74, 111, 165, 0.14);
}

.settings-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr 1fr;
}

.span-2 {
  grid-column: span 2;
}

.field {
  margin-bottom: 16px;
}

.field label {
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 6px;
}

.dim {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.8;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.dl-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}

.dl-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 12px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.25s ease-out;
}

.dl-item:hover {
  border-color: rgba(74, 111, 165, 0.4);
}

.dl-item.selected {
  border-color: rgba(74, 111, 165, 0.5);
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(180, 120, 140, 0.12));
}

.dl-check {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.75);
  display: grid;
  place-items: center;
  font-size: 11px;
  color: transparent;
}

.dl-check.on {
  background: rgba(74, 111, 165, 0.85);
  color: #fff;
  border-color: transparent;
}

.dl-name {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.update-result {
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.7;
}

.voice-dl-stage {
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(255, 215, 122, 0.12);
  border: 1px solid rgba(255, 215, 122, 0.4);
  border-radius: 10px;
  font-size: 12px;
  color: #b07a3a;
}

.update-line {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.update-review {
  color: #b07a3a;
  margin-top: 6px;
}

.update-error {
  color: #c05a5a;
  margin-top: 6px;
  white-space: pre-wrap;
}

.plugin-group {
  margin-bottom: 14px;
}

.group-title {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 6px;
}

.plugin-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 14px;
}

/* ---- 水彩卡片皮肤：对齐主页面右侧 .panel-card 观感 ---- */
.wc-card {
  background: rgba(255, 255, 255, 0.6) !important;
  border: 1px solid var(--line) !important;
  border-radius: 14px !important;
  box-shadow: var(--shadow-soft) !important;
}
.wc-card > .n-card-header {
  padding: 14px 16px 10px;
}
.wc-card > .n-card-header .n-card-header__main {
  color: var(--ink);
  font-family: var(--font-serif);
  font-weight: 300;
  letter-spacing: 2px;
  font-size: 14px;
}
.wc-card > .n-card__content {
  padding: 6px 16px 16px;
  color: var(--ink);
}

/* 设置页顶部大标题与主页一致 */
.page-header h1 {
  font-family: var(--font-serif);
  font-weight: 300;
  letter-spacing: 4px;
  font-size: 22px;
}

/* Naive 输入框水彩化（纸感浅底已在全局 themeOverrides，这里强化边框） */
.wc-card .n-input, .wc-card .n-select, .wc-card .n-input-number {
  --n-border: 1px solid rgba(74, 111, 165, 0.28);
  --n-border-hover: 1px solid rgba(74, 111, 165, 0.55);
  --n-border-focus: 1px solid rgba(74, 111, 165, 0.7);
}

/* checkbox 与标签颜色统一 */
.wc-card .n-checkbox__label {
  color: var(--ink);
  font-weight: 300;
}

/* ---- 主题选择器 ---- */
.theme-picker {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.theme-opt {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 1;
  min-width: 140px;
  padding: 10px 16px;
  border-radius: 14px;
  border: 1.5px solid rgba(74, 111, 165, 0.25);
  background: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  user-select: none;
  transition: border-color 0.3s ease-out, box-shadow 0.3s ease-out, background 0.3s ease-out;
}
.theme-opt:hover {
  border-color: rgba(74, 111, 165, 0.5);
  box-shadow: var(--shadow-soft);
}
.theme-opt.active {
  border-color: rgba(74, 111, 165, 0.6);
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.1), rgba(133, 205, 202, 0.1));
  box-shadow: var(--shadow-soft);
}
.theme-swatch {
  width: 26px;
  height: 26px;
  flex: none;
  border-radius: 50%;
  border: 1px solid rgba(120, 120, 120, 0.25);
}
.theme-swatch-watercolor {
  background:
    radial-gradient(60% 60% at 30% 30%, rgba(74, 111, 165, 0.85), transparent 70%),
    radial-gradient(60% 60% at 70% 65%, rgba(133, 205, 202, 0.85), transparent 70%),
    linear-gradient(135deg, #faf8f5, #f0ebe3);
}
.theme-swatch-shoujo {
  background:
    radial-gradient(60% 60% at 30% 30%, rgba(255, 183, 197, 0.9), transparent 70%),
    radial-gradient(60% 60% at 70% 65%, rgba(196, 181, 253, 0.9), transparent 70%),
    linear-gradient(135deg, #fff5f7, #ffe9ee);
}
.theme-swatch-cyberpunk {
  background:
    radial-gradient(60% 60% at 30% 30%, rgba(34, 211, 238, 0.95), transparent 70%),
    radial-gradient(60% 60% at 70% 65%, rgba(232, 121, 249, 0.9), transparent 70%),
    linear-gradient(135deg, #0a0a0f, #0d0d15);
}
.theme-swatch-solarpunk {
  background:
    radial-gradient(60% 60% at 30% 30%, rgba(74, 222, 128, 0.95), transparent 70%),
    radial-gradient(60% 60% at 70% 65%, rgba(251, 191, 36, 0.9), transparent 70%),
    linear-gradient(135deg, #f0fdf4, #dcfce7);
}
.theme-name {
  font-size: 13px;
  letter-spacing: 1px;
  color: var(--ink);
}
.theme-check {
  margin-left: auto;
  width: 14px;
  flex: none;
  color: var(--blue);
  font-weight: 600;
  font-size: 13px;
  opacity: 0;
  transition: opacity 0.2s ease-out;
}
.theme-check.show {
  opacity: 1;
}
body.theme-shoujo .theme-opt {
  border-color: rgba(255, 183, 197, 0.35);
  background: #fff;
}
body.theme-shoujo .theme-opt.active {
  border-color: rgba(244, 114, 160, 0.6);
  background: linear-gradient(135deg, rgba(255, 183, 197, 0.18), rgba(196, 181, 253, 0.14));
}
body.theme-shoujo .theme-check {
  color: #f472a0;
}

/* ---- 关于卡片 ---- */.about-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.about-logo {
  width: 44px;
  height: 44px;
  flex: none;
  display: grid;
  place-items: center;
  font-size: 22px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(133, 205, 202, 0.18));
  border: 1px solid rgba(74, 111, 165, 0.3);
  box-shadow: var(--shadow-soft);
}
.about-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.about-name {
  font-family: var(--font-serif);
  font-size: 16px;
  letter-spacing: 2px;
  color: var(--ink);
}
.about-version {
  font-size: 11.5px;
  letter-spacing: 1px;
  color: var(--gold-deep, #a8862f);
  background: rgba(201, 168, 76, 0.16);
  display: inline-flex;
  align-items: center;
  padding: 1px 10px;
  border-radius: 999px;
  width: fit-content;
}
.about-desc {
  margin: 0 0 10px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--ink);
}
.about-desc b {
  font-weight: 400;
  color: var(--blue);
}
.about-sec {
  font-size: 11.5px;
  letter-spacing: 2px;
  color: var(--muted);
  margin: 12px 0 6px;
  padding-bottom: 5px;
  border-bottom: 1px dashed rgba(74, 111, 165, 0.25);
}
.about-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12.5px;
  line-height: 2;
  color: var(--ink);
}
.about-list li::marker {
  color: var(--blue);
}
.about-foot {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px dashed rgba(74, 111, 165, 0.25);
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--muted);
}
</style>
