<template>
  <div ref="wrapRef" class="spine-wrap">
    <canvas ref="canvasRef" class="spine-canvas"></canvas>
    <!-- 诊断心跳：每帧更新时间/动画/暂停状态。定格时看它还在不在跳：在跳=渲染输出停；不跳=rAF 停 -->
    <div class="spine-dbg" :class="{ hidden: !debugOn }">{{ dbgText }}</div>
  </div>
</template>

<script setup>
import { onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { assetUrl } from '../bridge'
import '../../../templates/wallpaper-layout.js'

const WL = window.WallpaperLayout

// NIKKE 贴图是预乘 alpha（atlas 页头 pma:true）：原样直传（浏览器不再预乘），
// drawSkeleton(skeleton, true) 按预乘混合（ONE / ONE_MINUS_SRC_ALPHA）绘制。
// 与导出模板 templates/wallpaper_spine.html 的 NIKKE_PREMULTIPLY_UPLOAD 保持一致。
const NIKKE_PREMULTIPLY_UPLOAD = false

const props = defineProps({
  skin: { type: Object, required: true },
  // 当前姿势的骨架配置（relative to asset.dir）：{skel, atlas}；为空用 asset.layers
  poseCfg: { type: Object, default: null },
  animation: { type: String, default: '' },
  scale: { type: Number, default: 100 },
  bgScale: { type: Number, default: 100 },
  offsetX: { type: Number, default: 0 },
  offsetY: { type: Number, default: 0 },
  charOffsetX: { type: Number, default: 0 },
  charOffsetY: { type: Number, default: 0 },
  bgOffsetX: { type: Number, default: 0 },
  bgOffsetY: { type: Number, default: 0 },
  adjustTarget: { type: String, default: 'stage' },
  alignment: { type: String, default: 'center' },
  // 该皮肤 skel 的 Spine 版本（4.0/4.1），决定加载哪个运行时
  spineVersion: { type: String, default: '4.1' },
})
const emit = defineEmits(['ready', 'error', 'animations', 'scaleChange', 'panChange', 'bgScaleChange', 'charOffsetChange', 'bgOffsetChange'])

const wrapRef = ref(null)
const dbgText = ref('')
const debugOn = ref(true)
const canvasRef = ref(null)

let gl = null
let renderer = null
let layers = []
let raf = 0
let lastFrame = 0
let disposed = false
let paused = false
let boundsCache = null
let drag = null
let _dc = 0

// ---- Spine 运行时按版本动态加载（NIKKE 骨骼 4.0/4.1 混用） ----
// index.html 不再静态引入运行时；这里按皮肤版本注入对应 vendor 文件。
// 两个版本都写 window.spine，同一时刻只保留一个版本（切换前清掉旧的）。
const runtimePromises = {}
function ensureRuntime(version) {
  // 版本判断：'4.0.47'/'4.0' → 4.0；其余 → 4.1（split('.')[0] 只会得到 '4'，不能用来区分）
  const v = String(version || '4.1').startsWith('4.0') ? '4.0' : '4.1'
  if (window.spine && window.__spineRuntimeVersion === v) return Promise.resolve()
  if (runtimePromises[v]) return runtimePromises[v]
  runtimePromises[v] = new Promise((resolve, reject) => {
    document.querySelectorAll('script[data-spine-runtime]').forEach((s) => s.remove())
    window.spine = undefined
    const s = document.createElement('script')
    s.src = `/vendor/spine-webgl-${v}.js`
    s.dataset.spineRuntime = v
    s.onload = () => {
      window.__spineRuntimeVersion = v
      resolve()
    }
    s.onerror = () => {
      delete runtimePromises[v]
      reject(new Error(`Spine 运行时加载失败: ${v}`))
    }
    document.head.appendChild(s)
  })
  return runtimePromises[v]
}

function curAnimName() {
  const l0 = layers.find((l) => l.skeleton && l.state)
  if (!l0) return ''
  const e = l0.state.getCurrent(0)
  return e && e.animation ? e.animation.name : ''
}

function clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, v))
}

function parseAtlasPages(text) {
  // 贴图名可能带 UTF-8 BOM（\ufeff），必须剥离，否则拼进 URL 会 404
  return [...text.matchAll(/^([^\r\n]+\.png)\s*$/gm)].map((m) => m[1].replace(/^\ufeff/, ''))
}

async function loadLayer(cfg) {
  const base = assetUrl(props.skin.asset.dir)
  // 姿势子目录（main/aim/cover）：atlas 与贴图都在姿势目录下，页面名相对它解析
  const poseDir = cfg.atlas.includes('/') ? cfg.atlas.slice(0, cfg.atlas.lastIndexOf('/')) : ''
  const texUrl = (page) => (poseDir ? `${base}/${poseDir}/${page}` : `${base}/${page}`)
  const atlasText = (await (await fetch(`${base}/${cfg.atlas}`)).text()).replace(/^\ufeff/, '')
  const pages = parseAtlasPages(atlasText)
  const images = {}
  await Promise.all(
    pages.map((p) => {
      return new Promise((resolve, reject) => {
        const img = new Image()
        img.onload = () => {
          images[p] = img
          resolve()
        }
        img.onerror = () => reject(new Error(`texture load failed: ${p}`))
        img.src = texUrl(p)
      })
    }),
  )
  const texMap = {}
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, NIKKE_PREMULTIPLY_UPLOAD)
  for (const p of pages) texMap[p] = new spine.GLTexture(gl, images[p])

  const atlas = new spine.TextureAtlas(atlasText)
  atlas.pages.forEach((page) => page.setTexture(texMap[page.name] || texMap[Object.keys(texMap)[0]]))
  const loader = new spine.AtlasAttachmentLoader(atlas)
  const skelBuf = await (await fetch(`${base}/${cfg.skel}`)).arrayBuffer()
  const data = new spine.SkeletonBinary(loader).readSkeletonData(new Uint8Array(skelBuf))
  const skeleton = new spine.Skeleton(data)
  // 选附件最多的 skin：default 优先，同数保持 default；部分皮肤 default 残缺
  skeleton.setSkin(bestSkin(data))
  skeleton.setSlotsToSetupPose()
  skeleton.updateWorldTransform()
  const state = new spine.AnimationState(new spine.AnimationStateData(data))
  return { skeleton, state, data, name: cfg.skel }
}

function bestSkin(data) {
  const skins = data.skins || []
  if (skins.length <= 1) return data.defaultSkin || skins[0]
  let best = data.defaultSkin || skins[0]
  let bestCount = -1
  for (const sk of skins) {
    let count = 0
    const skel = new spine.Skeleton(data)
    skel.setSkin(sk)
    skel.setSlotsToSetupPose()
    skel.updateWorldTransform()
    for (const slot of skel.slots) {
      const att = slot.getAttachment()
      if (!att) continue
      if (slot.color && slot.color.a < 0.01) continue
      if ((att.name || '').toLowerCase().startsWith('kkkkk')) continue
      count++
    }
    if (count > bestCount) {
      bestCount = count
      best = sk
    }
  }
  return best
}

function pickAnim(data) {
  const names = data.animations.map((a) => a.name)
  // 默认动画：优先常驻的循环/待机（loop_*/idle/normal），避免转场开场取景框错
  const loop = names.find((n) => /^loop/i.test(n))
  const idle = names.find((n) => /idle/i.test(n)) || names.find((n) => n === 'normal')
  return loop || idle || names[0] || ''
}

function playAnimation(name) {
  if (!layers.length) return
  for (const l of layers) {
    if (!l.skeleton) continue
    const t = !name ? pickAnim(l.data) : (l.data.animations.some((a) => a.name === name) ? name : pickAnim(l.data))
    if (t) l.state.setAnimation(0, t, true)
  }
}

function isBgLayer(l) {
  // 多骨架分层兼容（NIKKE 单骨架时自动空转）
  if (!l || !l.skeleton || !l.name) return false
  return /b(?:g)?\d*$/i.test(l.name.replace(/\.skel$/i, ''))
}

// 插槽级背景面板过滤：内嵌全屏背景网格/黑边面板不参与取景（兼容 BD2 遗留规则）
function isBgPanelSlot(slot) {
  const cache = slot._bp
  if (cache !== undefined) return cache
  const nm = ((slot.data && slot.data.name) || '').toLowerCase().trim()
  slot._bp = nm === 'bk' || nm === 'bg' || nm.indexOf('b_bg') === 0 || nm.indexOf('bg_') === 0 || nm.indexOf('bg-') === 0
  return slot._bp
}

function layerBounds(l) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const slot of l.skeleton.slots) {
    const att = slot.getAttachment()
    if (!att) continue
    if (slot.color && slot.color.a < 0.01) continue
    if ((att.name || '').toLowerCase().startsWith('kkkkk')) continue
    if (isBgPanelSlot(slot) || slot._maskPanel) continue
    const isRegion = att instanceof spine.RegionAttachment
    if (!isRegion && !(att instanceof spine.MeshAttachment) && !(att instanceof spine.BoundingBoxAttachment)) continue
    const len = isRegion ? 8 : att.worldVerticesLength
    if (!len) continue
    const verts = spine.Utils.newFloatArray(len)
    if (isRegion) att.computeWorldVertices(slot, verts, 0, 2)
    else att.computeWorldVertices(slot, 0, len, verts, 0, 2)
    for (let j = 0; j < len; j += 2) {
      if (verts[j] < minX) minX = verts[j]
      if (verts[j] > maxX) maxX = verts[j]
      if (verts[j + 1] < minY) minY = verts[j + 1]
      if (verts[j + 1] > maxY) maxY = verts[j + 1]
    }
  }
  return { minX, maxX, minY, maxY }
}

function contentFrame() {
  // 按附件面积加权的网格密度取景：只框住"内容密集"区域，
  // 用于骨架包围盒被大面积背景网格/稀疏光效撑爆、角色被"挤"小的皮肤
  const raw = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
  const items = []
  for (const l of layers) {
    if (!l.skeleton) continue
    for (const slot of l.skeleton.slots) {
      const att = slot.getAttachment()
      if (!att) continue
      if (slot.color && slot.color.a < 0.01) continue
      if ((att.name || '').toLowerCase().startsWith('kkkkk')) continue
      if (isBgPanelSlot(slot) || slot._maskPanel) continue
      const isRegion = att instanceof spine.RegionAttachment
      const isMesh = att instanceof spine.MeshAttachment
      if (!isRegion && !isMesh) continue
      const len = isRegion ? 8 : att.worldVerticesLength
      if (!len) continue
      const verts = spine.Utils.newFloatArray(len)
      if (isRegion) att.computeWorldVertices(slot, verts, 0, 2)
      else att.computeWorldVertices(slot, 0, len, verts, 0, 2)
      const b = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
      for (let j = 0; j < len; j += 2) {
        if (verts[j] < b.minX) b.minX = verts[j]
        if (verts[j] > b.maxX) b.maxX = verts[j]
        if (verts[j + 1] < b.minY) b.minY = verts[j + 1]
        if (verts[j + 1] > b.maxY) b.maxY = verts[j + 1]
      }
      items.push(b)
      if (b.minX < raw.minX) raw.minX = b.minX
      if (b.maxX > raw.maxX) raw.maxX = b.maxX
      if (b.minY < raw.minY) raw.minY = b.minY
      if (b.maxY > raw.maxY) raw.maxY = b.maxY
    }
  }
  if (!items.length) return null
  const rawW = raw.maxX - raw.minX
  const rawH = raw.maxY - raw.minY
  const N = 64
  const gw = rawW / N || 1
  const gh = rawH / N || 1
  const grid = new Float64Array(N * N)
  for (const b of items) {
    const cx = (b.minX + b.maxX) / 2
    const cy = (b.minY + b.maxY) / 2
    const gx = Math.min(N - 1, Math.max(0, Math.floor((cx - raw.minX) / gw)))
    const gy = Math.min(N - 1, Math.max(0, Math.floor((cy - raw.minY) / gh)))
    grid[gy * N + gx] += Math.max(1, (b.maxX - b.minX) * (b.maxY - b.minY))
  }
  let maxCell = 0
  for (const v of grid) if (v > maxCell) maxCell = v
  if (!maxCell) return null
  const threshold = maxCell * 0.02
  let fminX = raw.maxX, fmaxX = raw.minX, fminY = raw.maxY, fmaxY = raw.minY, kept = 0
  for (let gy = 0; gy < N; gy++) {
    for (let gx = 0; gx < N; gx++) {
      if (grid[gy * N + gx] >= threshold) {
        kept++
        if (raw.minX + gx * gw < fminX) fminX = raw.minX + gx * gw
        if (raw.minX + (gx + 1) * gw > fmaxX) fmaxX = raw.minX + (gx + 1) * gw
        if (raw.minY + gy * gh < fminY) fminY = raw.minY + gy * gh
        if (raw.minY + (gy + 1) * gh > fmaxY) fmaxY = raw.minY + (gy + 1) * gh
      }
    }
  }
  const fW = fmaxX - fminX
  const fH = fmaxY - fminY
  const ratioW = fW / rawW
  const ratioH = fH / rawH
  if (!kept || ratioW > 0.55 || ratioH > 0.55 || ratioW < 0.08 || ratioH < 0.08) return null
  const padX = fW * 0.15
  const padY = fH * 0.15
  return { minX: fminX - padX, maxX: fmaxX + padX, minY: fminY - padY, maxY: fmaxY + padY }
}

function denseAreaFrame() {
  // 面积过滤取景：保留面积 ≤ 最大附件 40% 的部件，滤掉超大背景/云朵。
  const raw = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
  const items = []
  for (const l of layers) {
    if (!l.skeleton) continue
    for (const slot of l.skeleton.slots) {
      const att = slot.getAttachment()
      if (!att) continue
      if (slot.color && slot.color.a < 0.01) continue
      if ((att.name || '').toLowerCase().startsWith('kkkkk')) continue
      if (isBgPanelSlot(slot) || slot._maskPanel) continue
      const isRegion = att instanceof spine.RegionAttachment
      const isMesh = att instanceof spine.MeshAttachment
      if (!isRegion && !isMesh) continue
      const len = isRegion ? 8 : att.worldVerticesLength
      if (!len) continue
      const verts = spine.Utils.newFloatArray(len)
      if (isRegion) att.computeWorldVertices(slot, verts, 0, 2)
      else att.computeWorldVertices(slot, 0, len, verts, 0, 2)
      const b = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
      for (let j = 0; j < len; j += 2) {
        if (verts[j] < b.minX) b.minX = verts[j]
        if (verts[j] > b.maxX) b.maxX = verts[j]
        if (verts[j + 1] < b.minY) b.minY = verts[j + 1]
        if (verts[j + 1] > b.maxY) b.maxY = verts[j + 1]
      }
      items.push(b)
      if (b.minX < raw.minX) raw.minX = b.minX
      if (b.maxX > raw.maxX) raw.maxX = b.maxX
      if (b.minY < raw.minY) raw.minY = b.minY
      if (b.maxY > raw.maxY) raw.maxY = b.maxY
    }
  }
  if (!items.length) return null
  const rawW = raw.maxX - raw.minX
  const rawH = raw.maxY - raw.minY
  const areas = items.map((b) => (b.maxX - b.minX) * (b.maxY - b.minY))
  const maxA = Math.max(...areas)
  if (maxA >= rawW * rawH * 0.8) return null
  const keep = items.filter((b, i) => areas[i] <= maxA * 0.4)
  if (!keep.length) return null
  const N = 64
  const gw = rawW / N || 1
  const gh = rawH / N || 1
  const grid = new Float64Array(N * N)
  for (const b of keep) {
    const cx = (b.minX + b.maxX) / 2
    const cy = (b.minY + b.maxY) / 2
    const gx = Math.min(N - 1, Math.max(0, Math.floor((cx - raw.minX) / gw)))
    const gy = Math.min(N - 1, Math.max(0, Math.floor((cy - raw.minY) / gh)))
    grid[gy * N + gx] += Math.max(1, (b.maxX - b.minX) * (b.maxY - b.minY))
  }
  let maxCell = 0
  for (const v of grid) if (v > maxCell) maxCell = v
  if (!maxCell) return null
  const threshold = maxCell * 0.02
  let fminX = raw.maxX, fmaxX = raw.minX, fminY = raw.maxY, fmaxY = raw.minY, keptCells = 0
  for (let gy = 0; gy < N; gy++) {
    for (let gx = 0; gx < N; gx++) {
      if (grid[gy * N + gx] >= threshold) {
        keptCells++
        if (raw.minX + gx * gw < fminX) fminX = raw.minX + gx * gw
        if (raw.minX + (gx + 1) * gw > fmaxX) fmaxX = raw.minX + (gx + 1) * gw
        if (raw.minY + gy * gh < fminY) fminY = raw.minY + gy * gh
        if (raw.minY + (gy + 1) * gh > fmaxY) fmaxY = raw.minY + (gy + 1) * gh
      }
    }
  }
  const fW = fmaxX - fminX
  const fH = fmaxY - fminY
  if (!keptCells || fW >= rawW * 0.9 || fH >= rawH * 0.9) return null
  const padX = fW * 0.12
  const padY = fH * 0.12
  return { minX: fminX - padX, maxX: fmaxX + padX, minY: fminY - padY, maxY: fmaxY + padY }
}

function computeBounds() {
  // 取景链：contentFrame（网格密度）→ denseAreaFrame（面积过滤）→ 兜底。
  // 只算一次并缓存：动画帧里的超大特效部件会瞬间撑爆边界。
  if (boundsCache) return boundsCache
  const dense = contentFrame()
  if (dense) {
    boundsCache = dense
    return boundsCache
  }
  const areaFrame = denseAreaFrame()
  if (areaFrame) {
    boundsCache = areaFrame
    return boundsCache
  }
  const per = layers.filter((l) => l.skeleton).map(layerBounds).filter((b) => Number.isFinite(b.minX))
  if (!per.length) {
    boundsCache = { minX: -1, maxX: 1, minY: -1, maxY: 1 }
    return boundsCache
  }
  let small = per[0]
  for (const b of per) {
    const a = (b.maxX - b.minX) * (b.maxY - b.minY)
    const ra = (small.maxX - small.minX) * (small.maxY - small.minY)
    if (a < ra) small = b
  }
  const baseArea = (small.maxX - small.minX) * (small.maxY - small.minY) || 1
  const frame = per.filter((b) => (b.maxX - b.minX) * (b.maxY - b.minY) <= baseArea * 4)
  boundsCache = {
    minX: Math.min(...frame.map((b) => b.minX)),
    maxX: Math.max(...frame.map((b) => b.maxX)),
    minY: Math.min(...frame.map((b) => b.minY)),
    maxY: Math.max(...frame.map((b) => b.maxY)),
  }
  return boundsCache
}

function applyLayout() {
  const canvas = canvasRef.value
  const cw = canvas.clientWidth
  const ch = canvas.clientHeight
  if (!cw || !ch || !layers.length || !renderer) return
  const a = WL.anchor(props.alignment)
  const cam = WL.spineCamera(computeBounds(), cw, ch, {
    scale: props.scale,
    offsetX: props.offsetX,
    offsetY: props.offsetY,
    alignX: a.x,
    alignY: a.y,
  })
  renderer.camera.zoom = cam.zoom
  renderer.camera.position.x = cam.x
  renderer.camera.position.y = cam.y
  renderer.camera.position.z = 0
}

function render() {
  const _l0 = layers.find((l) => l.skeleton && l.state)
  let _t = 'no-skel'
  if (_l0) {
    const _e = _l0.state.getCurrent(0)
    if (_e && _e.animation) _t = `${_e.animation.name}@${_e.trackTime.toFixed(1)}s${_e.loop ? '(loop)' : ''}`
    else _t = 'no-anim'
  }
  dbgText.value = `帧${++_dc} ${_t}${paused ? ' PAUSED' : ''}${disposed ? ' DISPOSED' : ''}`.slice(0, 90)
  if (disposed || paused) {
    if (!disposed && paused) raf = 0
    return
  }
  try {
    const now = performance.now() / 1000
    const delta = Math.min(0.1, now - lastFrame)
    lastFrame = now
    const canvas = canvasRef.value
    if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
      canvas.width = canvas.clientWidth
      canvas.height = canvas.clientHeight
      gl.viewport(0, 0, canvas.width, canvas.height)
      renderer.camera.setViewport(canvas.width, canvas.height)
      applyLayout()
    }
    const _cw = canvas.clientWidth || 1
    const _ch = canvas.clientHeight || 1
    const _zoom = renderer.camera.zoom || 1
    const _charOff = WL.charOffsetWorld(props.charOffsetX, props.charOffsetY, _cw, _ch, _zoom)
    for (const l of layers) {
      if (!l.skeleton) continue
      try {
        if (!isBgLayer(l) && (_charOff.x || _charOff.y)) {
          l.skeleton.x = (l.charBaseX ?? l.skeleton.x) + _charOff.x
          l.skeleton.y = (l.charBaseY ?? l.skeleton.y) + _charOff.y
        } else {
          if (l.charBaseX !== undefined) l.skeleton.x = l.charBaseX
          if (l.charBaseY !== undefined) l.skeleton.y = l.charBaseY
        }
        l.state.update(delta)
        l.state.apply(l.skeleton)
        l.skeleton.updateWorldTransform()
      } catch (e) {
        console.warn('[spine-render] 层动画异常:', l.name, e)
      }
    }
    gl.clearColor(0, 0, 0, 0)
    gl.clear(gl.COLOR_BUFFER_BIT)
    renderer.begin()
    for (const l of layers) {
      if (!l.skeleton) continue
      renderer.drawSkeleton(l.skeleton, true)
    }
    renderer.end()
  } catch (e) {
    console.error('[spine-render] 帧内异常:', e.message || e)
    if (!disposed) emit('error', '[spine-render] ' + (e.message || String(e)))
  }
  raf = requestAnimationFrame(render)
}

watch(
  () => [props.scale, props.bgScale, props.offsetX, props.offsetY, props.alignment],
  () => applyLayout(),
)

watch(
  () => props.animation,
  (v) => v && playAnimation(v),
)

function onCanvasWheel(e) {
  e.preventDefault()
  const factor = Math.pow(1.1, -e.deltaY / 100)
  if (props.adjustTarget === 'bg') {
    const nextBg = Math.max(30, Math.min(300, Math.round(props.bgScale * factor)))
    if (nextBg !== props.bgScale) emit('bgScaleChange', nextBg)
    return
  }
  const next = Math.round(WL.clampScale(props.scale * factor))
  emit('scaleChange', next)
}

function onCanvasDown(e) {
  if (e.button !== 0) return
  e.preventDefault()
  if (props.adjustTarget === 'char' || props.adjustTarget === 'bg') {
    const isChar = props.adjustTarget === 'char'
    drag = {
      x: e.clientX,
      y: e.clientY,
      target: props.adjustTarget,
      ox: isChar ? props.charOffsetX : props.bgOffsetX,
      oy: isChar ? props.charOffsetY : props.bgOffsetY,
    }
    canvasRef.value.style.cursor = 'move'
    return
  }
  drag = {
    x: e.clientX,
    y: e.clientY,
    ox: props.offsetX,
    oy: props.offsetY,
    camX: renderer.camera.position.x,
    camY: renderer.camera.position.y,
    zoom: renderer.camera.zoom,
  }
  canvasRef.value.style.cursor = 'grabbing'
}

function onMove(e) {
  if (!drag) return
  drag.lastX = e.clientX
  drag.lastY = e.clientY
  if (drag.target === 'char' || drag.target === 'bg') {
    const canvas = canvasRef.value
    const cw = canvas.clientWidth || 1
    const ch = canvas.clientHeight || 1
    const nx = WL.clampOffset(drag.ox + ((e.clientX - drag.x) / cw) * 100)
    const ny = WL.clampOffset(drag.oy - ((e.clientY - drag.y) / ch) * 100)
    if (drag.target === 'char') emit('charOffsetChange', { x: nx, y: ny })
    else emit('bgOffsetChange', { x: nx, y: ny })
    return
  }
  const cam = renderer.camera
  const dx = e.clientX - drag.x
  const dy = e.clientY - drag.y
  cam.position.x = drag.camX - dx * drag.zoom
  cam.position.y = drag.camY + dy * drag.zoom
  cam.position.z = 0
}

function onUp() {
  if (!drag) return
  const canvas = canvasRef.value
  const cw = canvas.clientWidth || 1
  const ch = canvas.clientHeight || 1
  const lx = drag.lastX != null ? drag.lastX : drag.x
  const ly = drag.lastY != null ? drag.lastY : drag.y
  if (drag.target === 'char' || drag.target === 'bg') {
    const target = drag.target
    const nx = Math.round(WL.clampOffset(drag.ox + ((lx - drag.x) / cw) * 100))
    const ny = Math.round(WL.clampOffset(drag.oy - ((ly - drag.y) / ch) * 100))
    drag = null
    canvas.style.cursor = 'grab'
    if (target === 'char') emit('charOffsetChange', { x: nx, y: ny })
    else emit('bgOffsetChange', { x: nx, y: ny })
    return
  }
  const ox = Math.round(WL.clampOffset(drag.ox + ((lx - drag.x) / cw) * 100))
  const oy = Math.round(WL.clampOffset(drag.oy - ((ly - drag.y) / ch) * 100))
  drag = null
  canvas.style.cursor = 'grab'
  emit('panChange', { x: ox, y: oy })
}

onMounted(async () => {
  try {
    await ensureRuntime(props.spineVersion)
    if (disposed) return
    const canvas = canvasRef.value
    canvas.width = canvas.clientWidth
    canvas.height = canvas.clientHeight
    gl =
      canvas.getContext('webgl', { alpha: true, premultipliedAlpha: true, preserveDrawingBuffer: true }) ||
      canvas.getContext('experimental-webgl', { alpha: true })
    if (!gl) throw new Error('WebGL not supported')
    renderer = new spine.SceneRenderer(canvas, gl, false)
    const cfgs = props.poseCfg ? [props.poseCfg] : (props.skin.asset.layers || [])
    const loaded = await Promise.all(cfgs.map((c) => loadLayer(c)))
    if (disposed) return
    layers = loaded
    const skelLayers = loaded.filter((l) => l.skeleton)
    playAnimation(props.animation || '')
    for (const l of skelLayers) {
      l.state.update(0)
      l.state.apply(l.skeleton)
      l.skeleton.updateWorldTransform()
    }
    for (const l of skelLayers) {
      l.charBaseX = l.skeleton.x
      l.charBaseY = l.skeleton.y
    }
    const anims = [...new Set(skelLayers.flatMap((l) => l.data.animations.map((a) => a.name)))]
    emit('animations', anims)
    applyLayout()
    const canvasEl = canvasRef.value
    canvasEl.style.cursor = 'grab'
    canvasEl.addEventListener('wheel', onCanvasWheel, { passive: false })
    canvasEl.addEventListener('mousedown', onCanvasDown)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    lastFrame = performance.now() / 1000
    emit('ready')
    raf = requestAnimationFrame(render)
  } catch (e) {
    if (!disposed) emit('error', e.message || String(e))
  }
})

// keep-alive 缓存（图鉴页）下切走时暂停渲染循环；切回时恢复
onDeactivated(() => {
  paused = true
  cancelAnimationFrame(raf)
  raf = 0
})
onActivated(() => {
  paused = false
  if (!disposed && layers.length && !raf) {
    lastFrame = performance.now() / 1000
    raf = requestAnimationFrame(render)
  }
})

onBeforeUnmount(() => {
  disposed = true
  paused = false
  cancelAnimationFrame(raf)
  raf = 0
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onUp)
  if (canvasRef.value) {
    canvasRef.value.removeEventListener('wheel', onCanvasWheel)
    canvasRef.value.removeEventListener('mousedown', onCanvasDown)
  }
  if (gl && renderer) renderer.dispose()
})

defineExpose({
  capture: () => {
    try {
      return canvasRef.value ? canvasRef.value.toDataURL('image/png') : null
    } catch (e) {
      return null
    }
  },
})
</script>

<style scoped>
.spine-wrap {
  position: relative;
  width: 100%;
  height: 100%;
}
.spine-canvas {
  width: 100%;
  height: 100%;
  display: block;
  touch-action: none;
  user-select: none;
}
.spine-dbg {
  position: absolute;
  top: 2px;
  left: 2px;
  z-index: 5;
  background: rgba(10, 14, 20, 0.75);
  color: #9fe09f;
  font: 10px/1.4 ui-monospace, Consolas, monospace;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
  pointer-events: none;
}
.spine-dbg.hidden { display: none; }
</style>
