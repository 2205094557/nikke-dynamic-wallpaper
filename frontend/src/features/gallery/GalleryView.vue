<template>
  <div class="main-view" :class="{ 'is-fullscreen': fullscreen }">
    <!-- 顶栏 -->
    <header class="main-topbar" v-if="!fullscreen">
      <div class="main-title">
        <h1>NIKKE · 壁纸工坊</h1>
        <span v-if="skinMode">共 {{ filteredSkins.length }} 个皮肤</span>
        <span v-else>共 {{ filtered.length }} 人 · {{ totalSkins }} 个皮肤</span>
      </div>
    </header>

    <div class="main-body">
      <!-- 左侧角色库 -->
      <aside class="ship-rail" v-if="!fullscreen">
        <n-input v-model:value="searchInput" placeholder="角色名 / 皮肤…" clearable size="small">
          <template #prefix>🔍</template>
        </n-input>
        <div class="rail-tools">
          <span class="rail-tool" :class="{ active: favOnly }" @click="favOnly = !favOnly">
            {{ favOnly ? '★ 只看收藏中' : '☆ 只看收藏' }}
          </span>
          <span class="rail-tool" :class="{ active: multiMode }" @click="toggleMulti">
            {{ multiMode ? '✓ 多选中' : '多选' }}
          </span>
        </div>
        <div ref="railListRef" class="rail-list">
          <template v-if="skinMode">
            <div
              v-for="item in filteredSkins"
              :key="item.skin.key"
              class="rail-card skin-row"
              :class="{ active: currentSkin && currentSkin.key === item.skin.key }"
              @click="onSkinClick(item)"
            >
              <div class="rail-avatar" :style="avatarStyle(item.ship)">
                <img v-if="avatarUrl(item.ship)" :src="avatarUrl(item.ship)" class="rail-avatar-img" @error="onAvatarError(item.ship)" />
                <span v-else class="rail-char">{{ item.ship.name[0] }}</span>
              </div>
              <div class="rail-info">
                <div class="rail-name">{{ item.ship.name }}</div>
                <div class="rail-skin" :title="item.skin.name">{{ item.skin.name }}</div>
                <div class="rail-meta">
                  <span class="wc-pill" :class="item.skin.type === 'spine' ? 'green' : 'blue'">
                    {{ item.skin.type === 'spine' ? 'Spine' : '静态' }}
                  </span>
                </div>
              </div>
              <span v-if="multiMode" class="rail-check" :class="{ on: isSelected(item.skin.key) }">✓</span>
            </div>
          </template>
          <template v-else>
            <div
              v-for="ship in filtered"
              :key="ship.id"
              class="rail-card"
              :class="{ active: ship.id === selectedId }"
              @click="onCardClick(ship)"
            >
              <div class="rail-avatar" :style="avatarStyle(ship)">
                <img v-if="avatarUrl(ship)" :src="avatarUrl(ship)" class="rail-avatar-img" @error="onAvatarError(ship)" />
                <span v-else class="rail-char">{{ ship.name[0] }}</span>
              </div>
              <div class="rail-info">
                <div class="rail-name">{{ ship.name }}</div>
                <div class="rail-meta">
                  <span v-for="t in shipTypes(ship)" :key="t" class="wc-pill green">Spine</span>
                </div>
              </div>
              <span v-if="multiMode" class="rail-check" :class="{ on: isSelected(ship.id) }">✓</span>
            </div>
          </template>
        </div>
      </aside>

      <!-- 中央预览区 -->
      <div class="preview-zone">
        <div ref="stageWrapRef" class="stage-wrap">
          <div ref="stageRef" class="preview-stage" :class="`bg-${bgStyle}`" :style="autoBgStyle">
            <SpinePreview
              v-if="currentSkin && currentSkin.type === 'spine' && currentSkin.asset"
              ref="previewEl"
              :key="currentSkin.key + '|' + currentPose"
              :skin="currentSkin"
              :pose-cfg="activePoseCfg"
              :spine-version="activeSpineVersion"
              :animation="animation"
              :scale="scale"
              :bg-scale="bgScale"
              :offset-x="offsetX"
              :offset-y="offsetY"
              :char-offset-x="charOffsetX"
              :char-offset-y="charOffsetY"
              :bg-offset-x="bgOffsetX"
              :bg-offset-y="bgOffsetY"
              :adjust-target="adjustTarget"
              :alignment="alignment"
              :enable-interaction="enableInteraction"
              @animations="onSpineAnims"
              @error="onEngineError"
              @scale-change="scale = $event"
              @pan-change="offsetX = $event.x; offsetY = $event.y"
              @bg-scale-change="bgScale = $event"
              @char-offset-change="charOffsetX = $event.x; charOffsetY = $event.y"
              @bg-offset-change="bgOffsetX = $event.x; bgOffsetY = $event.y"
            />
            <StaticPreview
              v-else-if="currentSkin && currentSkin.type === 'static' && currentSkin.asset"
              :key="currentSkin.key"
              :skin="currentSkin"
              :scale="scale"
              :offset-x="offsetX"
              :offset-y="offsetY"
              @scale-change="scale = $event"
              @pan-change="offsetX = $event.x; offsetY = $event.y"
              @error="onEngineError"
            />
            <div v-else class="preview-placeholder">
              <div class="preview-halo"></div>
              <div class="preview-title">{{ selectedShip ? selectedShip.name : '选择角色' }} · {{ currentSkin ? currentSkin.name : '' }}</div>
              <div class="preview-sub">
                {{ currentSkin && currentSkin.status === 'remote' ? '未下载（下载后可预览）' : '点击左侧角色开始预览' }}
              </div>
            </div>
            <div v-if="selectedShip && currentSkin" class="stage-info">
              <span class="stage-info-name">{{ selectedShip.name }}</span>
              <span class="stage-info-skin">{{ currentSkin.name }}</span>
            </div>
            <div v-if="currentSkin && (currentSkin.type === 'spine')" class="l2d-panel-a">
              <div class="adjust-seg" :class="'at-' + adjustTarget" title="选择拖动/滚轮作用对象：画面(整体锁定) / 人物 / 背景">
                <div class="adjust-seg-thumb"></div>
                <button class="adjust-seg-item" :class="{ active: adjustTarget === 'stage' }" title="拖动平移整体画面，滚轮整体等比缩放" @click="adjustTarget = 'stage'">画面</button>
                <button class="adjust-seg-item" :class="{ active: adjustTarget === 'char' }" title="拖动只移动人物，滚轮只缩放人物" @click="adjustTarget = 'char'">人物</button>
                <button class="adjust-seg-item" :class="{ active: adjustTarget === 'bg' }" title="拖动只移动背景，滚轮只缩放背景" @click="adjustTarget = 'bg'">背景</button>
              </div>
            </div>
            <span class="zoom-hint">角色 {{ scale }}% · 背景 {{ bgScale }}%<template v-if="adjustTarget !== 'stage'"> · 调节{{ adjustTarget === 'char' ? '人物' : '背景' }}</template></span>
            <button class="stage-fullscreen-btn" @click="toggleFullscreen" :title="fullscreen ? '退出全屏' : '全屏预览'">
              {{ fullscreen ? '✕' : '⛶' }}
            </button>
          </div>
        </div>

        <!-- 皮肤切换条 -->
        <div class="skin-bar">
          <div class="skin-strip">
            <div
              v-for="(skin, i) in (selectedShip ? selectedShip.skins : [])"
              :key="skin.key"
              class="skin-chip"
              :class="{ active: i === currentSkinIndex }"
              @click="currentSkinIndex = i"
            >
              {{ skin.name }}
            </div>
            <span v-if="selectedShip && !selectedShip.skins.length" class="bar-dim">无皮肤</span>
          </div>
          <div class="skin-status">
            <template v-if="selectedShip">
              <button
                v-if="currentSkin && currentSkin.status === 'remote' && canDownload(currentSkin)"
                class="wc-btn gradient dl-btn"
                :disabled="downloading"
                @click="downloadCurrent"
              >
                {{ downloading ? '下载中…' : '下载当前' }}
              </button>
              <span v-else-if="currentSkin && currentSkin.status === 'downloaded'" class="dl-ok">✓ 当前已下载</span>
              <span v-else-if="currentSkin && currentSkin.status === 'remote' && !canDownload(currentSkin)" class="bar-dim">
                暂不支持
              </span>
              <button
                v-if="hasRemote(selectedShip)"
                class="wc-btn gradient dl-btn"
                :disabled="allDownloading"
                @click="downloadAll"
              >
                {{ allDownloading ? `下载全部 ${allDone}/${allTotal}` : '下载全部' }}
              </button>
              <button
                v-if="currentSkin"
                class="skin-fav-btn"
                :class="{ on: isSkinFav(currentSkin.key) }"
                :title="isSkinFav(currentSkin.key) ? '取消收藏该皮肤' : '收藏该皮肤'"
                @click="toggleSkinFav(currentSkin.key)"
              >
                {{ isSkinFav(currentSkin.key) ? '★' : '☆' }}
              </button>
            </template>
          </div>
        </div>
      </div>

      <!-- 右侧控制面板 -->
      <aside class="control-panel" v-if="!fullscreen">
        <div class="panel-card">
          <div class="panel-title">外观</div>
          <div class="panel-field">
            <label>背景</label>
            <div class="bg-select-box">
              <div class="bg-select-main">
                <n-select v-model:value="bgStyle" :options="bgOptions" size="small" style="width: 100%" />
                <input
                  v-if="bgStyle === 'solid'"
                  v-model="solidColor"
                  type="color"
                  class="solid-picker"
                  title="自定义纯色背景"
                />
              </div>
              <div v-if="bgStyle === 'image'" class="bg-current-row">
                <div class="bg-current-name" :title="selectedBgName || '未选择背景'">
                  {{ selectedBgName || '未选择背景' }}
                </div>
                <button
                  class="wc-btn small bg-change-btn"
                  @click="bgModalOpen = true"
                  title="选择官方场景背景"
                >
                  更换图
                </button>
              </div>

              <!-- 扩图合成工作流：导出到 output → 外部工具扩图 → 成品放进 input → 导入 -->
              <div v-if="bgStyle === 'image'" class="bg-outpaint-bar">
                <div class="bg-outpaint-steps">
                  <span class="bg-outpaint-title">扩图合成</span>
                  <span class="dim">① 导出到 output → ② 外部扩图 → ③ 成品放 input → ④ 导入</span>
                </div>
                <div class="bg-outpaint-actions">
                  <button
                    class="wc-btn small"
                    :disabled="!selectedBgImage || outpaintExporting"
                    @click="doExportOutpaint"
                    title="把当前所选背景（含已超分版本）复制到 output 文件夹，供 Photoshop 生成式扩展 / Stable Diffusion 等外部工具扩图（不会自动弹出文件夹）"
                  >
                    {{ outpaintExporting ? '导出中…' : '📤 导出扩图' }}
                  </button>
                  <button
                    class="wc-btn small"
                    :disabled="importingOutpaint"
                    @click="doImportOutpaint"
                    title="只扫描 input 文件夹：把里面的扩图成品收进自定义背景库（非 png 自动转 png），随后即可超分、合成、导出壁纸"
                  >
                    {{ importingOutpaint ? '导入中…' : '📥 导入扩图' }}
                  </button>
                  <button
                    class="wc-btn small bg-outpaint-folder"
                    @click="openOutputFolder"
                    title="打开 output 文件夹（导出待扩图的原始背景）"
                  >
                    📁 output
                  </button>
                  <button
                    class="wc-btn small bg-outpaint-folder"
                    @click="openInputFolder"
                    title="打开 input 文件夹（把扩图成品放进来，导入只识别这里）"
                  >
                    📁 input
                  </button>
                </div>
              </div>
            </div>
            <!-- 背景超分设置精致卡片 -->
            <div v-if="bgStyle === 'image'" class="bg-upscale-card">
              <div class="bg-upscale-card-head">
                <span class="bg-upscale-badge">✨ AI 背景超分</span>
                <div class="head-actions">
                  <span v-if="selectedBgIsCustom" class="bg-scale-tag custom-tag" title="来自自定义 / 扩图背景库">自定义</span>
                  <span v-if="selectedBgUpscaleTag" class="bg-scale-tag">{{ selectedBgUpscaleTag }}</span>
                  <button
                    class="bg-adv-toggle-btn"
                    :class="{ on: showUpscaleAdv }"
                    @click="showUpscaleAdv = !showUpscaleAdv"
                    title="展开/收起高级超分参数（降噪、TTA增强、超采样）"
                  >
                    ⚙️ 参数
                  </button>
                </div>
              </div>
              <div class="bg-upscale-inputs">
                <div class="upscale-select-row">
                  <n-select
                    v-model:value="upscaleAlgo"
                    :options="upscaleAlgoOptions"
                    size="small"
                    style="flex: 1; min-width: 0;"
                    title="选择 AI 超分引擎"
                  />
                  <n-select
                    v-model:value="upscaleScale"
                    :options="[
                      { label: '2x 放大', value: 2 },
                      { label: '4x 超清', value: 4 }
                    ]"
                    size="small"
                    style="width: 86px; flex-shrink: 0;"
                    title="选择放大倍率"
                  />
                </div>

                <!-- 高级自定义参数折叠区 -->
                <div v-if="showUpscaleAdv" class="upscale-adv-drawer">
                  <div class="adv-param-item">
                    <span class="adv-label">降噪级别</span>
                    <n-select
                      v-model:value="upscaleDenoise"
                      :options="denoiseOptions"
                      size="tiny"
                      style="flex: 1"
                    />
                  </div>
                  <div class="adv-param-item adv-switch-item">
                    <span class="adv-label" title="8个旋转方向采样取平均值，画面杂讯更少但耗时增加约 2~3 倍">TTA 多角度采样</span>
                    <n-switch v-model:value="upscaleTta" size="small" />
                  </div>
                  <div v-if="upscaleScale === 2" class="adv-param-item adv-switch-item">
                    <span class="adv-label" title="先以 4x 极清渲染再高质量重采样回 2x，纹理比直接 2x 更致密">4x$\rightarrow$2x 超采样</span>
                    <n-switch v-model:value="upscaleDownsample" size="small" />
                  </div>
                </div>

                <button
                  class="wc-btn gradient block bg-upscale-submit-btn"
                  :disabled="upscalingBg || !selectedBgImage"
                  @click="doUpscaleCurrentBg(upscaleScale, upscaleAlgo)"
                  title="使用所选 AI 引擎对当前背景执行超分高清化"
                >
                  {{ upscalingBg ? '正在深度计算…' : '⚡ 生成超分背景' }}
                </button>
              </div>
            </div>
          </div>
          <div class="panel-field">
            <label>动画</label>
            <n-select
              v-model:value="animation"
              :options="animOptions"
              size="small"
              :disabled="!animOptions.length"
              placeholder="无"
              style="width: 100%"
            />
            <div v-if="animOptions.length" class="anim-nav">
              <button class="wc-btn anim-nav-btn" @click="stepAnim(-1)">←</button>
              <span class="anim-nav-label">{{ animIndex + 1 }} / {{ animOptions.length }}</span>
              <button class="wc-btn anim-nav-btn" @click="stepAnim(1)">→</button>
            </div>
          </div>
          <div class="panel-field">
            <label>姿势</label>
            <n-select
              v-model:value="currentPose"
              :options="poseOptions"
              size="small"
              :disabled="!poseOptions.length"
              placeholder="无"
              style="width: 100%"
            />
          </div>
          <div class="panel-field">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <label style="margin: 0;">点击互动</label>
              <n-switch v-model:value="enableInteraction" size="small" />
            </div>
            <span class="dim" style="font-size: 11px; margin-top: 4px; display: block;">
              开启后点击角色触发动作与表情循环互动；关闭则保持安静待机。
            </span>
          </div>
        </div>

        <div class="panel-card">
          <div class="panel-title">导出</div>
          <template v-if="currentSkin">
            <!-- 互动控制面板可用（Spine 皮肤）：只保留人物/背景两组详细调节，
                 整体偏移/对齐方式/壁纸类型由画布拖拽模式与默认值接管，不再显示 -->
            <template v-if="currentSkin.type !== 'static'">
              <div class="panel-group">
                <div class="panel-group-title">人物调节</div>
                <div class="panel-field">
                  <label title="只移动角色骨架，背景保持不动">位置 · 水平</label>
                  <div class="offset-row">
                    <n-slider v-model:value="charOffsetX" :min="-100" :max="100" :step="1" />
                    <span class="bar-value" :class="{ zero: charOffsetX === 0 }">{{ charOffsetX > 0 ? '+' : '' }}{{ charOffsetX }}</span>
                  </div>
                </div>
                <div class="panel-field">
                  <label>位置 · 垂直</label>
                  <div class="offset-row">
                    <n-slider v-model:value="charOffsetY" :min="-100" :max="100" :step="1" />
                    <span class="bar-value" :class="{ zero: charOffsetY === 0 }">{{ charOffsetY > 0 ? '+' : '' }}{{ charOffsetY }}</span>
                  </div>
                </div>
                <div class="panel-field">
                  <label>缩放 <span class="bar-dim">{{ scale }}%</span></label>
                  <n-slider v-model:value="scale" :min="20" :max="300" :step="5" />
                </div>
              </div>
              <div class="panel-group">
                <div class="panel-group-title">背景调节</div>
                <div class="panel-field">
                  <label title="独立调节背景图大小（100 = 默认铺满画布视口）">缩放 <span class="bar-dim">{{ bgScale }}%</span></label>
                  <div class="offset-row">
                    <n-slider v-model:value="bgScale" :min="30" :max="300" :step="5" />
                    <button class="wc-btn reset-bgscale" @click="bgScale = 100" title="重置背景缩放">重置</button>
                  </div>
                </div>
                <div class="panel-field">
                  <label title="只移动背景图，人物保持不动">位置 · 水平</label>
                  <div class="offset-row">
                    <n-slider v-model:value="bgOffsetX" :min="-100" :max="100" :step="1" />
                    <span class="bar-value" :class="{ zero: bgOffsetX === 0 }">{{ bgOffsetX > 0 ? '+' : '' }}{{ bgOffsetX }}</span>
                  </div>
                </div>
                <div class="panel-field">
                  <label>位置 · 垂直</label>
                  <div class="offset-row">
                    <n-slider v-model:value="bgOffsetY" :min="-100" :max="100" :step="1" />
                    <span class="bar-value" :class="{ zero: bgOffsetY === 0 }">{{ bgOffsetY > 0 ? '+' : '' }}{{ bgOffsetY }}</span>
                  </div>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="panel-field">
                <label>水平偏移（占画布宽 %）</label>
                <div class="offset-row">
                  <n-slider v-model:value="offsetX" :min="-100" :max="100" :step="1" />
                  <span class="bar-value" :class="{ zero: offsetX === 0 }">{{ offsetX > 0 ? '+' : '' }}{{ offsetX }}</span>
                </div>
              </div>
              <div class="panel-field">
                <label>垂直偏移（占画布高 %）</label>
                <div class="offset-row">
                  <n-slider v-model:value="offsetY" :min="-100" :max="100" :step="1" />
                  <span class="bar-value" :class="{ zero: offsetY === 0 }">{{ offsetY > 0 ? '+' : '' }}{{ offsetY }}</span>
                </div>
              </div>
              <div class="panel-field">
                <label>缩放 <span class="bar-dim">{{ scale }}%</span></label>
                <n-slider v-model:value="scale" :min="20" :max="300" :step="5" />
              </div>
              <div class="panel-field">
                <label>对齐方式</label>
                <n-select
                  v-model:value="alignment"
                  :options="[
                    { label: '居中', value: 'center' },
                    { label: '左上', value: 'left-top' },
                    { label: '右上', value: 'right-top' },
                    { label: '左下', value: 'left-bottom' },
                    { label: '右下', value: 'right-bottom' },
                  ]"
                  size="small"
                  style="width: 100%"
                />
              </div>
            </template>
            <div class="panel-field">
              <button class="wc-btn preset-import-btn" @click="openPresetImport">📥 导入 WE 预设 JSON</button>
            </div>
            <n-modal v-model:show="presetImportOpen" preset="card" title="导入 Wallpaper Engine 预设" style="width: 520px; max-width: 92vw">
              <p class="dim" style="margin-bottom: 10px">
                在 Wallpaper Engine 属性面板点「分享预设」复制内容（JSON 或 Base64 均可），
                粘贴到下面，即可把 缩放 / 偏移 / 对齐 应用到当前预览。
              </p>
              <n-input
                v-model:value="presetImportText"
                type="textarea"
                :rows="8"
                placeholder='{"scalectrl": 244, "offsetx": 8, "offsety": 4, "alignment": "center"}'
                style="font-family: var(--font-mono, Consolas, monospace); font-size: 12px"
              />
              <div class="preset-modal-actions">
                <n-button size="small" @click="presetImportOpen = false">取消</n-button>
                <n-button size="small" type="primary" @click="applyWePreset">应用</n-button>
              </div>
            </n-modal>
            <div class="export-actions">
              <button
                v-if="currentSkin.type !== 'static'"
                class="wc-btn gradient block"
                :disabled="!currentSkin.asset || exporting"
                @click="doExport"
              >
                {{ exporting ? '导出中…' : '导出动态壁纸' }}
              </button>
              <button class="wc-btn gradient block" :disabled="!currentSkin.asset || applying" @click="doApply">
                {{ applying ? '正在导出并应用…' : '导出并应用' }}
              </button>
            </div>
            <p v-if="currentSkin && !currentSkin.asset" class="panel-tip">请先下载该皮肤，再导出壁纸</p>
            <template v-if="applyDone">
              <n-alert v-if="applyResult && applyResult.ok" type="success" :show-icon="true" class="export-alert">
                已应用：{{ applyResult.project }}
              </n-alert>
              <n-alert v-else type="error" :show-icon="true" class="export-alert">
                应用失败：{{ (applyResult && applyResult.error) || '未知错误' }}
              </n-alert>
            </template>
            <template v-if="exportDone">
              <n-alert v-if="exportResult && exportResult.ok" type="success" :show-icon="true" class="export-alert">
                导出完成：{{ exportResult.project }}
              </n-alert>
              <n-alert v-else type="error" :show-icon="true" class="export-alert">
                导出失败：{{ (exportResult && exportResult.error) || '未知错误' }}
              </n-alert>
            </template>
          </template>
        </div>

        <div class="panel-card">
          <div class="panel-title">其他功能</div>
          <div class="panel-nav">
            <button
              class="wc-btn panel-nav-btn"
              :class="{ active: route.path === '/gallery' }"
              @click="router.push('/gallery')"
            >
              ⚓ 角色图鉴
            </button>
            <button
              class="wc-btn panel-nav-btn"
              :class="{ active: route.path === '/settings' }"
              @click="router.push('/settings')"
            >
              ⚙ 设置
            </button>
          </div>
        </div>
      </aside>
    </div>

    <div v-if="multiMode" class="batch-bar">
      <span>已选 {{ selectedSet.size }} {{ skinMode ? '个' : '人' }}</span>
      <n-button size="small" type="primary" :disabled="!selectedSet.size" :loading="batchDownloading" @click="batchDownload">
        {{ batchDownloading ? `下载中 ${batchDone}/${batchTotal}` : '批量下载所选' }}
      </n-button>
      <button class="wc-btn gold batch-btn" @click="selectAllFiltered">全选</button>
      <button class="wc-btn gold batch-btn" @click="clearSelection">清空</button>
    </div>

    <div v-if="downloadMsg" class="download-msg">{{ downloadMsg }}</div>

    <div v-if="dlProgress.active" class="dl-progress-card">
      <div class="dl-progress-head">
        <span class="dl-progress-label">{{ dlProgress.label }}</span>
        <button class="wc-btn danger-soft dl-progress-cancel" :disabled="cancelling" @click="onCancelDownloads">
          {{ cancelling ? '正在取消…' : '取消' }}
        </button>
      </div>
      <div class="dl-progress-track">
        <div class="dl-progress-fill" :style="{ width: dlPct + '%' }"></div>
      </div>
      <div class="dl-progress-meta">
        {{ dlProgress.done + dlProgress.failed }}/{{ dlProgress.total }}
        <span v-if="dlProgress.failed">（{{ dlProgress.failed }} 失败）</span>
        <span v-if="cancelling">正在停止…</span>
      </div>
      <div v-if="dlStage" class="dl-progress-stage">{{ dlStage }}</div>
    </div>

    <!-- 官方背景选择弹窗 -->
    <n-modal
      v-model:show="bgModalOpen"
      preset="card"
      title="选择官方场景背景"
      style="width: 820px; max-width: 94vw; max-height: 85vh; display: flex; flex-direction: column;"
    >
      <div class="bg-selector-modal">
        <!-- 搜索与分类导航 -->
        <div class="bg-selector-toolbar">
          <div class="bg-selector-top">
            <n-input
              v-model:value="bgSearchQuery"
              placeholder="搜索场景名称或文件名..."
              size="small"
              clearable
              style="max-width: 240px"
            />
            <div class="bg-selector-dir-actions">
              <button
                class="wc-btn small open-bg-folder-btn"
                :disabled="importingOutpaint"
                @click="doImportOutpaint"
                title="只扫描 input 文件夹：把扩图成品导入自定义背景库，导入后在「自定义 / 扩图」分类中选用"
              >
                📥 导入扩图结果
              </button>
              <button class="wc-btn small open-bg-folder-btn" @click="openOutputFolder" title="打开 output 文件夹（导出待扩图的原始背景）">
                📁 output
              </button>
              <button class="wc-btn small open-bg-folder-btn" @click="openInputFolder" title="打开 input 文件夹（把扩图成品放进来，导入只识别这里）">
                📁 input
              </button>
              <button class="wc-btn small open-bg-folder-btn" @click="openCustomFolder" title="打开自定义背景库目录（在此可手动删除导入的背景）">
                📁 自定义库
              </button>
              <button class="wc-btn small open-bg-folder-btn" @click="openBackgroundFolder" title="打开官方背景目录，可手动放入更多场景图">
                📁 官方背景
              </button>
            </div>
          </div>
          <div class="bg-cat-tabs">
            <button
              class="bg-cat-pill"
              :class="{ active: bgActiveCategory === 'all' }"
              @click="bgActiveCategory = 'all'"
            >
              全部 ({{ allBackgrounds.length }})
            </button>
            <button
              v-if="recommendedBgs.length"
              class="bg-cat-pill rec-pill"
              :class="{ active: bgActiveCategory === 'recommended' }"
              @click="bgActiveCategory = 'recommended'"
            >
              ⭐ 专属推荐 ({{ recommendedBgs.length }})
            </button>
            <button
              v-for="cat in bgCategories"
              :key="cat.id"
              class="bg-cat-pill"
              :class="{ active: bgActiveCategory === cat.id }"
              @click="bgActiveCategory = cat.id"
            >
              {{ cat.name }}
            </button>
          </div>
        </div>

        <!-- 专属推荐置顶快捷卡片区 -->
        <div v-if="bgActiveCategory !== 'recommended' && recommendedBgs.length > 0 && !bgSearchQuery" class="bg-rec-section">
          <div class="bg-rec-title">✨ 当前角色剧情推荐：</div>
          <div class="bg-rec-grid">
            <div
              v-for="bgFn in recommendedBgs.slice(0, 6)"
              :key="'rec-' + bgFn"
              class="bg-card rec-card"
              :class="{ selected: selectedBgImage === bgFn }"
              @click="selectBg({ filename: bgFn })"
            >
              <img :src="getBgThumbUrl(bgFn)" class="bg-card-thumb" loading="lazy" decoding="async" />
              <div class="bg-card-info">
                <span class="bg-card-name" :title="bgFn">{{ getBgDisplayName(bgFn) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 主图片网格（虚拟分批按需渲染） -->
        <div class="bg-grid-container" @scroll="onBgGridScroll">
          <div v-if="filteredBackgrounds.length === 0" class="bg-empty-tip">
            <template v-if="bgActiveCategory === 'custom'">
              自定义背景库还是空的：点「📤 导出扩图」把当前背景导出到 output 文件夹，
              外部工具扩图后把成品放进 input 文件夹，再点「📥 导入扩图」，结果就会出现在这里。
            </template>
            <template v-else>未找到匹配的场景背景</template>
          </div>
          <div v-else class="bg-grid">
            <div
              v-for="item in displayedBackgrounds"
              :key="item.filename"
              class="bg-card"
              :class="{ selected: selectedBgImage === item.filename }"
              @click="selectBg(item)"
            >
              <img :src="getBgThumbUrl(item)" class="bg-card-thumb" loading="lazy" decoding="async" />
              <span v-if="item.source === 'custom'" class="bg-card-badge">自定义</span>
              <button
                v-if="item.source === 'custom'"
                class="bg-card-del"
                :class="{ armed: pendingDeleteBg === item.filename }"
                :title="pendingDeleteBg === item.filename ? '再点一次确认删除（文件将移出背景库，不可恢复）' : '删除这张自定义背景（同名官方背景会自动恢复可见）'"
                @click.stop="deleteCustomBg(item)"
              >
                {{ pendingDeleteBg === item.filename ? '确认删除' : '✕' }}
              </button>
              <div class="bg-card-info">
                <span class="bg-card-name" :title="item.filename">{{ item.name }}</span>
              </div>
            </div>
          </div>
          <div v-if="displayedBackgrounds.length < filteredBackgrounds.length" class="bg-more-tip">
            正在加载更多背景... ({{ displayedBackgrounds.length }} / {{ filteredBackgrounds.length }})
          </div>
        </div>
      </div>
    </n-modal>

  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NInput, NModal, NSelect, NSlider, NSwitch, NAlert } from 'naive-ui'
import { assetUrl, bridge, metadataUrl, sseUrl } from '../../bridge'
import { playChime, warmAudio } from '../../utils/sound'
import SpinePreview from '../../components/SpinePreview.vue'
import StaticPreview from '../../components/StaticPreview.vue'

const route = useRoute()
const router = useRouter()

const ships = ref([])
const loading = ref(true)
const selectedId = ref(null)
const railListRef = ref(null)
const currentSkinIndex = ref(0)
const fullscreen = ref(false)
const exporting = ref(false)
const exportDone = ref(false)
const exportResult = ref(null)
const applying = ref(false)
const applyDone = ref(false)
const applyResult = ref(null)
const downloading = ref(false)
const allDownloading = ref(false)
const allDone = ref(0)
const allTotal = ref(0)
const allFailed = ref(0)
const downloadMsg = ref('')
const skinFavs = ref(new Set())
const favOnly = ref(false)
const avatars = ref({})
const avatarFailed = ref(new Set())
// avatars.json 的加载时间戳：拼到图片 URL 上，头像更新后重新加载图片（避免浏览器缓存旧图）
const avatarsStamp = ref(0)
const multiMode = ref(false)
const selectedSet = ref(new Set())
const batchDownloading = ref(false)
const batchDone = ref(0)
const batchTotal = ref(0)
const batchFailed = ref(0)
const batchCancelled = ref(0)
const downloadBatchId = ref('')
const cancelling = ref(false)
const dlProgress = reactive({ active: false, done: 0, total: 0, failed: 0, cancelled: 0, label: '' })
const dlStage = ref('')
let dlSource = null
const previewEl = ref(null)

const batchPct = computed(() => {
  if (!batchTotal.value) return 0
  const d = batchDone.value + batchFailed.value + batchCancelled.value
  return Math.min(100, Math.round((d / batchTotal.value) * 100))
})
const dlPct = computed(() => {
  if (!dlProgress.total) return 0
  const d = dlProgress.done + dlProgress.failed + dlProgress.cancelled
  return Math.min(100, Math.round((d / dlProgress.total) * 100))
})
const SKIN_FAV_KEY = 'nk_wallpaper_skin_favs'
let msgTimer = null
let exportTimer = null
let applyTimer = null
const stageWrapRef = ref(null)
const stageRef = ref(null)
let stageRO = null

const STAGE_RATIO = 16 / 9

function fitStage() {
  const wrap = stageWrapRef.value
  const stage = stageRef.value
  if (!wrap || !stage) return
  const w = wrap.clientWidth
  const h = wrap.clientHeight
  if (!w || !h) return
  let sw = w
  let sh = sw / STAGE_RATIO
  if (sh > h) {
    sh = h
    sw = sh * STAGE_RATIO
  }
  stage.style.width = `${Math.floor(sw)}px`
  stage.style.height = `${Math.floor(sh)}px`
}

function showMsg(text) {
  downloadMsg.value = text
  clearTimeout(msgTimer)
  msgTimer = setTimeout(() => {
    downloadMsg.value = ''
  }, 5000)
}

const filters = reactive({ search: '', type: 'all' })
const bgStyle = ref('image') // 默认使用官方背景图
const animation = ref('')
const animOptions = ref([])
const scale = ref(100)
const bgScale = ref(100)
const offsetX = ref(0)
const offsetY = ref(0)
const charOffsetX = ref(0)
const charOffsetY = ref(0)
// 背景图独立位移（%）：只移动背景图（与角色位置独立调节对应）
const bgOffsetX = ref(0)
const bgOffsetY = ref(0)
// 画布拖拽/滚轮的调节对象：'stage'=整体画面（默认） | 'char'=人物 | 'bg'=背景
const adjustTarget = ref('stage')
const alignment = ref('center')
const enableInteraction = ref(true)
// 姿势（main/aim/cover）：本地资源按姿势独立成组，预览/导出共用
const currentPose = ref('main')
const POSE_LABELS = { main: '大厅', aim: '瞄准', cover: '封面' }
const poseOptions = computed(() => {
  const poses = currentSkin.value && currentSkin.value.asset && currentSkin.value.asset.poses
  return poses ? Object.keys(poses).map((p) => ({ label: POSE_LABELS[p] || p, value: p })) : []
})
const activePoseCfg = computed(() => {
  const asset = currentSkin.value && currentSkin.value.asset
  const poses = asset && asset.poses
  if (!poses) return null
  const pose = poses[currentPose.value] ? currentPose.value : (poses.main ? 'main' : Object.keys(poses)[0])
  return { skel: poses[pose].skel, atlas: poses[pose].atlas }
})
const activeSpineVersion = computed(() => {
  const asset = currentSkin.value && currentSkin.value.asset
  const poses = asset && asset.poses
  const pose = activePoseCfg.value
  if (poses && pose) {
    const key = Object.keys(poses).find((k) => poses[k].skel === pose.skel)
    if (key && poses[key].version) return poses[key].version
  }
  return (asset && asset.spine_version) || '4.1'
})
// WE 预设导入：粘贴 Wallpaper Engine「分享 JSON」的预设，应用到预览布局
const presetImportOpen = ref(false)
const presetImportText = ref('')
const ALIGN_VALUES = ['center', 'left-top', 'right-top', 'left-bottom', 'right-bottom']

function openPresetImport() {
  presetImportText.value = ''
  presetImportOpen.value = true
}

// 解析 WE 分享预设 JSON 并应用到预览（scalectrl/offsetx/offsety/alignment/开关）。
// 兼容两种格式：明文 JSON，或 WE「分享预设」的 Base64 编码（UTF-8）。
function applyWePreset() {
  let data
  const raw = (presetImportText.value || '').trim()
  try {
    data = JSON.parse(raw)
  } catch (e) {
    // 明文 JSON 解析失败 → 尝试 Base64 解码（WE 分享预设可切换 Base64 格式）
    try {
      const bin = atob(raw.replace(/\s+/g, ''))
      const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0))
      data = JSON.parse(new TextDecoder().decode(bytes))
    } catch (e2) {
      showMsg('无法解析：既不是 JSON，也不是 Base64 编码的 JSON')
      return
    }
  }
  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    showMsg('JSON 必须是对象格式')
    return
  }
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))
  const num = (v) => {
    const n = parseFloat(v)
    return Number.isFinite(n) ? n : null
  }
  let applied = 0
  const sc = num(data.scalectrl)
  if (sc !== null) { scale.value = Math.round(clamp(sc, 20, 300)); applied++ }
  const ox = num(data.offsetx)
  if (ox !== null) { offsetX.value = Math.round(clamp(ox, -100, 100)); applied++ }
  const oy = num(data.offsety)
  if (oy !== null) { offsetY.value = Math.round(clamp(oy, -100, 100)); applied++ }
  const cox = num(data.charoffsetx)
  if (cox !== null) { charOffsetX.value = Math.round(clamp(cox, -100, 100)); applied++ }
  const coy = num(data.charoffsety)
  if (coy !== null) { charOffsetY.value = Math.round(clamp(coy, -100, 100)); applied++ }
  // alignment 兼容 WE 的两种格式：数字下标（旧）或字符串对齐名（新）
  if (data.alignment !== undefined && data.alignment !== null) {
    const a = data.alignment
    const name = typeof a === 'number'
      ? (ALIGN_VALUES[a] || null)
      : (typeof a === 'string' && ALIGN_VALUES.includes(a) ? a : null)
    if (name) { alignment.value = name; applied++ }
  }
  if (applied) {
    showMsg(`已应用 ${applied} 项 WE 预设`)
    presetImportOpen.value = false
  } else {
    showMsg('未识别到可应用属性（scalectrl / offsetx / offsety / charoffsetx / charoffsety / alignment）')
  }
}
const bgOptions = [
  { label: '官方背景图', value: 'image' },
  { label: '自动取色', value: 'auto' },
  { label: '纯色', value: 'solid' },
  { label: '莫奈渐变', value: 'monet' },
  { label: '毛玻璃', value: 'frost' },
  { label: '星空', value: 'star' },
]

const totalSkins = computed(() => ships.value.reduce((n, s) => n + s.skins.length, 0))

const filtered = computed(() => {
  return ships.value.filter((s) => {
    const kw = filters.search.trim().toLowerCase()
    const skinHit = kw && s.skins.some((k) => (k.name || '').toLowerCase().includes(kw))
    if (
      kw &&
      !s.name.toLowerCase().includes(kw) &&
      !(s.en || '').toLowerCase().includes(kw) &&
      !pyText(s.py).includes(kw) &&
      !s.skins.some((k) => pyText(k.py).includes(kw)) &&
      !skinHit
    ) return false
    const types = new Set(s.skins.map((k) => k.type))
    if (filters.type !== 'all' && !types.has(filters.type)) return false
    return true
  })
})

// 按类型筛选时左侧改为皮肤级列表：直接展示具体的皮肤条目
// 只看收藏时同样切到皮肤级列表，展示的是收藏的单个皮肤
const skinMode = computed(() => filters.type !== 'all' || favOnly.value)

const filteredSkins = computed(() => {
  const out = []
  const kw = filters.search.trim().toLowerCase()
  for (const ship of filtered.value) {
    for (const skin of ship.skins) {
      if (filters.type !== 'all' && skin.type !== filters.type) continue
      if (favOnly.value && !skinFavs.value.has(skin.key)) continue
      if (
        kw &&
        !ship.name.toLowerCase().includes(kw) &&
        !(ship.en || '').toLowerCase().includes(kw) &&
        !pyText(ship.py).includes(kw) &&
        !(skin.name || '').toLowerCase().includes(kw) &&
        !pyText(skin.py).includes(kw)
      ) {
        continue
      }
      out.push({ ship, skin })
    }
  }
  return out
})

function clearFilters() {
  searchInput.value = ''
  filters.search = ''
  filters.type = 'all'
}

// 搜索框防抖：输入时不实时全量扫描数千条数据，停顿 250ms 后再过滤
const searchInput = ref('')
let searchTimer = null
watch(searchInput, (v) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    filters.search = v
  }, 250)
})

watch(() => filters.type, () => clearSelection())

const selectedShip = computed(() => ships.value.find((s) => s.id === selectedId.value) || null)
const currentSkin = computed(() => selectedShip.value?.skins[currentSkinIndex.value] || null)
// 切换皮肤时重置姿势与动画选择（每个皮肤可下载的姿势集不同）
//（watch 注册时会立即求值一次 getter，必须放在 currentSkin 定义之后）
watch(
  () => currentSkin.value && currentSkin.value.key,
  () => {
    currentPose.value = 'main'
    animOptions.value = []
    animation.value = ''
  },
)

const bgCss = ref('')
const solidColor = ref('')
const selectedBgImage = ref('') // 当前选中的官方背景文件名，如 'CrownCastleFrontYard_d.png'
const bgModalOpen = ref(false)
const allBackgrounds = ref([])
const bgCategories = ref([])
const recommendedBgs = ref([])
const bgActiveCategory = ref('all')
const bgSearchQuery = ref('')
const bgRenderLimit = ref(40)

function onBgGridScroll(e) {
  const el = e.target
  if (!el) return
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 150) {
    if (bgRenderLimit.value < filteredBackgrounds.value.length) {
      bgRenderLimit.value += 40
    }
  }
}

watch([bgActiveCategory, bgSearchQuery], () => {
  bgRenderLimit.value = 40
})

function getBgDisplayName(filename) {
  if (!filename) return ''
  const item = allBackgrounds.value.find((b) => b.filename === filename)
  return item ? item.name : filename.replace(/\.[^.]+$/, '')
}

const selectedBgName = computed(() => {
  if (!selectedBgImage.value) return ''
  return getBgDisplayName(selectedBgImage.value)
})

const filteredBackgrounds = computed(() => {
  let list = allBackgrounds.value
  if (bgActiveCategory.value === 'recommended') {
    const recSet = new Set(recommendedBgs.value)
    list = list.filter((b) => recSet.has(b.filename))
  } else if (bgActiveCategory.value !== 'all') {
    list = list.filter((b) => b.category === bgActiveCategory.value)
  }
  const q = bgSearchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter((b) => b.name.toLowerCase().includes(q) || b.filename.toLowerCase().includes(q))
  }
  return list
})

const displayedBackgrounds = computed(() => {
  return filteredBackgrounds.value.slice(0, bgRenderLimit.value)
})

function getBgThumbUrl(itemOrFilename) {
  const fn = typeof itemOrFilename === 'object' ? itemOrFilename.filename : itemOrFilename
  if (!fn) return ''
  // 后端为每条背景给出缩略图相对路径（自定义背景导入时已生成）
  if (typeof itemOrFilename === 'object' && itemOrFilename.thumb) {
    return assetUrl(itemOrFilename.thumb)
  }
  if (fn.includes('_preview.')) {
    return assetUrl(`preview/${fn}`)
  }
  const baseStem = fn.replace(/\.[^.]+$/, '')
  return assetUrl(`thumbnails/background/${baseStem}.webp`)
}

// 背景文件相对 resources/ 的路径：自定义库优先，其次官方，超分产物在 preview
function bgRelPath(itemOrFilename) {
  const fn = typeof itemOrFilename === 'object' ? itemOrFilename.filename : itemOrFilename
  if (!fn) return ''
  const isCustom =
    (typeof itemOrFilename === 'object' && itemOrFilename.source === 'custom') ||
    allBackgrounds.value.some((b) => b.filename === fn && b.source === 'custom')
  if (isCustom) return `custom/${fn}`
  if (fn.includes('_preview.')) return `preview/${fn}`
  return `background/${fn}`
}

function getBgImageUrl(filename) {
  if (!filename) return ''
  return assetUrl(bgRelPath(filename))
}

// 当前背景是否来自自定义 / 扩图库（超分预览名会回查母图归属）
const selectedBgIsCustom = computed(() => {
  const fn = selectedBgImage.value
  if (!fn) return false
  const hit = allBackgrounds.value.find((b) => b.filename === fn)
  if (hit) return hit.source === 'custom'
  const baseStem = fn.replace(/(_[a-zA-Z0-9]+_\d+x.*_preview|_\d+x)+$/i, '')
  return allBackgrounds.value.some(
    (b) => b.source === 'custom' && b.filename.replace(/\.[^.]+$/, '') === baseStem,
  )
})

// 超分产物文件名里带有 _preview 标记，据此展示倍率标签（避免误判普通文件名里的 _2x）
const selectedBgUpscaleTag = computed(() => {
  const fn = selectedBgImage.value
  if (!fn || !fn.includes('_preview.')) return ''
  if (fn.includes('_4x')) return '已 4x'
  if (fn.includes('_2x')) return '已 2x'
  return '已超分'
})

async function loadBackgrounds() {
  try {
    const shipName = selectedShip.value ? (selectedShip.value.en || selectedShip.value.name) : ''
    const res = await bridge.getBackgrounds({ ship: shipName })
    if (res && res.ok) {
      allBackgrounds.value = res.backgrounds || []
      bgCategories.value = res.categories || []
      recommendedBgs.value = res.recommendations || []
      // 切换人物后，若处于官方背景图模式，自动应用该角色的第 1 个剧情专属推荐背景
      if (bgStyle.value === 'image' && recommendedBgs.value.length > 0) {
        selectedBgImage.value = recommendedBgs.value[0]
      }
    }
  } catch (e) {
    console.error('加载背景列表失败:', e)
  }
}

function selectBg(bgItem) {
  selectedBgImage.value = bgItem.filename
  bgStyle.value = 'image'
  bgModalOpen.value = false
  refreshBg()
}

async function openBackgroundFolder() {
  const res = await bridge.openBackgroundDir()
  if (res && res.ok) {
    showMsg('已打开官方背景目录，放入图片后重新打开弹窗即可显示')
  } else {
    showMsg((res && res.error) || '打开背景目录失败')
  }
}

async function openOutputFolder() {
  const res = await bridge.openOutputDir()
  if (!res || !res.ok) showMsg((res && res.error) || '打开 output 文件夹失败')
}

async function openInputFolder() {
  const res = await bridge.openInputDir()
  if (!res || !res.ok) showMsg((res && res.error) || '打开 input 文件夹失败')
}

async function openCustomFolder() {
  const res = await bridge.openCustomBgDir()
  if (!res || !res.ok) showMsg((res && res.error) || '打开自定义库失败')
}

// 扩图工作流 ①：把当前背景（含已超分版本）导出到 output 文件夹（不自动打开文件夹，避免每次导出都弹窗）
async function doExportOutpaint() {
  if (!selectedBgImage.value) return
  outpaintExporting.value = true
  try {
    const res = await bridge.exportBgForOutpaint(selectedBgImage.value)
    if (res && res.ok) {
      showMsg(`✓ ${res.message || '已导出到 output 文件夹'}`)
    } else {
      showMsg(`✗ 导出失败：${(res && res.error) || '未知错误'}`)
    }
  } catch (e) {
    showMsg(`✗ 导出异常：${e.message || e}`)
  } finally {
    outpaintExporting.value = false
  }
}

// 扩图工作流 ④：扫描 input 文件夹，把成品导入自定义背景库，并直接选中第一张
async function doImportOutpaint() {
  importingOutpaint.value = true
  try {
    const res = await bridge.importOutpaintResults()
    if (!(res && res.ok)) {
      showMsg(`✗ 导入失败：${(res && res.error) || '未知错误'}`)
      return
    }
    showMsg(`✓ ${res.message || '导入完成'}`)
    const imported = res.imported || []
    if (!imported.length) {
      bgActiveCategory.value = 'custom'
      bgModalOpen.value = true
      return
    }
    await loadBackgrounds()
    bgStyle.value = 'image'
    selectedBgImage.value = imported[0]
    bgActiveCategory.value = 'custom'
    bgModalOpen.value = true
  } catch (e) {
    showMsg(`✗ 导入异常：${e.message || e}`)
  } finally {
    importingOutpaint.value = false
  }
}

// 自定义背景卡片删除：首次点击进入确认态，再次点击才真正删除
function deleteCustomBg(item) {
  if (pendingDeleteBg.value !== item.filename) {
    pendingDeleteBg.value = item.filename
    clearTimeout(pendingDeleteTimer)
    pendingDeleteTimer = setTimeout(() => {
      pendingDeleteBg.value = ''
    }, 4000)
    return
  }
  pendingDeleteBg.value = ''
  clearTimeout(pendingDeleteTimer)
  ;(async () => {
    const res = await bridge.deleteCustomBg(item.filename)
    if (res && res.ok) {
      showMsg(`✓ ${res.message || '已删除'}`)
      if (selectedBgImage.value === item.filename) selectedBgImage.value = ''
      await loadBackgrounds()
    } else {
      showMsg(`✗ 删除失败：${(res && res.error) || '未知错误'}`)
    }
  })()
}

const upscaleAlgo = ref('waifu2x')
const upscaleScale = ref(2)
const showUpscaleAdv = ref(false)
const upscaleDenoise = ref(0)
const upscaleTta = ref(false)
const upscaleDownsample = ref(false)
// 超分进行中标志（模板用它禁用按钮并显示进度文案）
const upscalingBg = ref(false)
// 扩图工作流：导出中转 / 导入入库 / 卡片二次确认删除
const outpaintExporting = ref(false)
const importingOutpaint = ref(false)
const pendingDeleteBg = ref('')
let pendingDeleteTimer = null

const denoiseOptions = [
  { label: '无降噪 (最锐利)', value: 0 },
  { label: '轻度降噪', value: 1 },
  { label: '中度降噪', value: 2 },
  { label: '强力去噪', value: 3 },
]

const upscaleAlgoOptions = [
  { label: 'Waifu2x (推荐，极佳兼容)', value: 'waifu2x' },
  { label: 'Real-CUGAN (二次元专属)', value: 'realcugan' },
  { label: 'Real-ESRGAN (精细渲染)', value: 'realesr' },
]

async function doUpscaleCurrentBg(scale = 2, algo = 'waifu2x') {
  if (!selectedBgImage.value) return
  upscalingBg.value = true
  try {
    const res = await bridge.upscaleBackground({
      filename: selectedBgImage.value,
      scale,
      algorithm: algo || upscaleAlgo.value,
      denoise: upscaleDenoise.value,
      tta: upscaleTta.value,
      downsample: upscaleDownsample.value && scale === 2,
    })
    if (res && res.ok && res.filename) {
      showMsg(res.message || `背景已成功放大 ${scale}x！`)
      // 重新拉取背景列表以包含新生成的图片
      await loadBackgrounds()
      selectedBgImage.value = res.filename
      bgStyle.value = 'image'
      refreshBg()
    } else {
      showMsg(`超分失败：${(res && res.error) || '未知错误'}`)
    }
  } catch (err) {
    showMsg(`超分请求异常：${err.message || err}`)
  } finally {
    upscalingBg.value = false
  }
}

const autoBgStyle = computed(() => {
  if (bgStyle.value === 'image' && selectedBgImage.value) {
    const url = getBgImageUrl(selectedBgImage.value)
    // 舞台尺寸
    const stage = stageRef.value
    const sw = (stage && stage.clientWidth) || 1280
    const sh = (stage && stage.clientHeight) || 720
    const scaleFactor = (bgScale.value || 100) / 100
    // 像素级偏移：bgOffsetX/Y 为占舞台宽高的百分比，直接转为精确像素
    const pxX = ((bgOffsetX.value || 0) / 100) * sw
    const pxY = -((bgOffsetY.value || 0) / 100) * sh
    return {
      backgroundImage: `url('${url}')`,
      backgroundSize: `${scaleFactor * 100}% auto`,
      backgroundPosition: `calc(50% + ${pxX}px) calc(50% + ${pxY}px)`,
      backgroundRepeat: 'no-repeat',
    }
  }
  return bgCss.value ? { background: bgCss.value } : {}
})

let bgSeq = 0
async function refreshBg() {
  const skin = currentSkin.value
  if (!skin) return
  const seq = ++bgSeq
  const res = await bridge.getPalette(skin.ship, skin.bundle, skin.name, {
    mode: bgStyle.value,
    bgColor: bgStyle.value === 'solid' ? solidColor.value || undefined : undefined,
  })
  if (seq !== bgSeq) return // 已有更新的取色请求：丢弃过期结果，避免旧皮肤/旧设置的颜色串到新皮肤上
  const raw = res && typeof res.css === 'string' ? res.css : ''
  // 后端返回的是完整声明（background: ...;），存进 CSS 变量时只保留值部分
  bgCss.value = raw.replace(/^background:\s*/, '').replace(/;\s*$/, '')
}

watch(currentSkin, () => {
  loadBackgrounds()
  refreshBg()
}, { immediate: true })
watch(currentSkin, () => {
  exportDone.value = false
  applyDone.value = false
  clearTimeout(exportTimer)
  clearTimeout(applyTimer)
})
watch(bgStyle, (newVal) => {
  if (newVal === 'image') {
    if (!selectedBgImage.value && recommendedBgs.value.length > 0) {
      selectedBgImage.value = recommendedBgs.value[0]
    }
  }
  refreshBg()
})
watch(solidColor, () => refreshBg())
watch(selectedBgImage, () => refreshBg())

const WC = ['74,111,165', '180,120,140', '120,160,130', '201,168,76']

function hashOf(name) {
  let h = 0
  for (const ch of name) h = (h * 31 + ch.codePointAt(0)) >>> 0
  return h
}

function avatarStyle(ship) {
  const c = WC[hashOf(ship.name) % 4]
  return { background: `linear-gradient(145deg, rgba(${c},0.42), rgba(240,235,227,0.7))` }
}

function avatarUrl(ship) {
  const f = avatars.value[ship.name]
  if (!f || avatarFailed.value.has(ship.name)) return ''
  // 拼时间戳：头像映射更新后（检查更新/重启）URL 变化，浏览器会重新拉取图片
  const stamp = avatarsStamp.value ? `?v=${avatarsStamp.value}` : ''
  return assetUrl(`avatars/${f}.jpg`) + stamp
}

function onAvatarError(ship) {
  const s = new Set(avatarFailed.value)
  s.add(ship.name)
  avatarFailed.value = s
}

// 拼音检索：匹配全拼（weikesibao）或首字母（wksb）
function pyText(py) {
  return py ? `${py.p || ''} ${py.i || ''}` : ''
}

function shipTypes(ship) {
  return [...new Set(ship.skins.map((k) => k.type))].filter((t) => t === 'spine')
}

function canDownload(skin) {
  return skin.type === 'spine' || skin.type === 'static'
}

function hasRemote(ship) {
  return ship.skins.some((k) => k.status === 'remote' && canDownload(k))
}

function getConcurrency() {
  try {
    const v = parseInt(localStorage.getItem('nk_concurrency') || '4', 10)
    return Math.min(8, Math.max(1, v || 4))
  } catch (e) {
    return 4
  }
}

let downloadCancelled = false

function newDownloadId() {
  return `dl_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function startDl(label, total) {
  downloadCancelled = false
  cancelling.value = false
  downloadBatchId.value = newDownloadId()
  dlProgress.active = true
  dlProgress.done = 0
  dlProgress.failed = 0
  dlProgress.cancelled = 0
  dlProgress.total = total
  dlProgress.label = label
  dlStage.value = ''
  if (dlSource) {
    dlSource.close()
    dlSource = null
  }
  // SSE：实时显示 下载立绘/合成/同步索引 等当前阶段（后端不支持时静默降级）
  try {
    dlSource = new EventSource(sseUrl())
    dlSource.addEventListener('stage', (e) => {
      try {
        const d = JSON.parse(e.data)
        dlStage.value = d.detail ? `${d.stage}：${d.detail}` : (d.stage || '')
      } catch (err) {
        /* 忽略异常事件 */
      }
    })
  } catch (err) {
    /* 后端未开 SSE 时静默 */
  }
}

function finishDl() {
  dlProgress.active = false
  downloadBatchId.value = ''
  if (dlSource) {
    dlSource.close()
    dlSource = null
  }
  dlStage.value = ''
}

async function onCancelDownloads() {
  if (downloadCancelled) return
  downloadCancelled = true
  cancelling.value = true
  if (downloadBatchId.value) {
    try {
      await bridge.cancelDownload(downloadBatchId.value)
    } catch (e) {
      /* 忽略取消请求失败，本地标志已生效 */
    }
  }
}

async function runDownloadPool(targets, limit, onProgress, batchId) {
  let done = 0
  const failedTargets = []
  let cancelledCount = 0
  let idx = 0
  const worker = async () => {
    while (idx < targets.length) {
      if (downloadCancelled) return
      const t = targets[idx++]
      try {
        const res = await bridge.downloadSkin(t.ship, t.bundle, t.name, batchId)
        if (res && res.cancelled) {
          cancelledCount++
        } else if (res && res.ok) {
          done++
        } else {
          failedTargets.push(t)
        }
      } catch (e) {
        if (downloadCancelled) cancelledCount++
        else failedTargets.push(t)
      }
      if (onProgress) onProgress({ done, failed: failedTargets.length, cancelled: cancelledCount })
    }
  }
  const n = Math.min(Math.max(1, limit), targets.length)
  await Promise.all(Array.from({ length: n }, worker))
  return { done, failedTargets, cancelled: downloadCancelled || cancelledCount > 0, cancelledCount }
}

// 失败的皮肤自动重试一轮，避免网络抖动导致批量下载"莫名失败"
async function runPoolWithRetry(targets, limit, onProgress, batchId) {
  const first = await runDownloadPool(targets, limit, (p) => {
    if (onProgress) onProgress(p)
  }, batchId)
  if (first.cancelled || !first.failedTargets.length) {
    return {
      done: first.done,
      failed: first.failedTargets.length,
      cancelled: first.cancelled,
      cancelledCount: first.cancelledCount,
    }
  }
  const second = await runDownloadPool(first.failedTargets, limit, (p) => {
    if (onProgress) onProgress({ done: first.done + p.done, failed: p.failed, cancelled: first.cancelledCount + p.cancelled })
  }, batchId)
  return {
    done: first.done + second.done,
    failed: second.failedTargets.length,
    cancelled: second.cancelled,
    cancelledCount: first.cancelledCount + second.cancelledCount,
  }
}

function selectShip(ship) {
  selectedId.value = ship.id
  currentSkinIndex.value = 0
  animOptions.value = []
  animation.value = ''
  currentPose.value = 'main'
}

function loadFavs() {
  try {
    skinFavs.value = new Set(JSON.parse(localStorage.getItem(SKIN_FAV_KEY) || '[]'))
  } catch (e) {
    skinFavs.value = new Set()
  }
}

function saveFavs() {
  localStorage.setItem(SKIN_FAV_KEY, JSON.stringify([...skinFavs.value]))
}

function isSkinFav(key) {
  return skinFavs.value.has(key)
}

function toggleSkinFav(key) {
  const s = new Set(skinFavs.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  skinFavs.value = s
  saveFavs()
}

function toggleMulti() {
  multiMode.value = !multiMode.value
  if (!multiMode.value) clearSelection()
}

function isSelected(id) {
  return selectedSet.value.has(id)
}

function toggleSelect(id) {
  const s = new Set(selectedSet.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedSet.value = s
}

function clearSelection() {
  selectedSet.value = new Set()
}

function selectAllFiltered() {
  if (skinMode.value) {
    for (const item of filteredSkins.value) selectedSet.value.add(item.skin.key)
  } else {
    for (const s of filtered.value) selectedSet.value.add(s.id)
  }
}

function onCardClick(ship) {
  if (multiMode.value) toggleSelect(ship.id)
  else selectShip(ship)
}

function selectSkinItem(item) {
  const ship = ships.value.find((s) => s.id === item.ship.id)
  if (!ship) return
  const idx = ship.skins.findIndex((k) => k.key === item.skin.key)
  if (idx < 0) return
  selectedId.value = ship.id
  currentSkinIndex.value = idx
  animOptions.value = []
  animation.value = ''
  currentPose.value = 'main'
}

function onSkinClick(item) {
  if (multiMode.value) {
    toggleSelect(item.skin.key)
    return
  }
  selectSkinItem(item)
}

// 上下键翻动左侧列表选中项（角色/皮肤切换）：按当前筛选列表移动选中位置，
// 再滚动到可见。与缩放无关（取景统一由方案 B 保证，切换角色不会缩放跳变）。
function railStep(dir) {
  const list = skinMode.value ? filteredSkins.value : filtered.value
  if (!list.length) return
  let cur = -1
  if (skinMode.value) {
    const key = currentSkin.value && currentSkin.value.key
    cur = list.findIndex((it) => it.skin.key === key)
  } else {
    cur = list.findIndex((s) => s.id === selectedId.value)
  }
  // 当前项不在筛选列表（搜索/筛选导致）时：next 从第一项开始，prev 从最后一项开始。
  // 原来的 (cur+dir+len)%len 在 cur=-1 时 prev 会算出 len-2，跳过头一项。
  const next = cur < 0 ? (dir > 0 ? 0 : list.length - 1) : (cur + dir + list.length) % list.length
  if (skinMode.value) selectSkinItem(list[next])
  else selectShip(list[next])
  // 键盘翻动后让左侧列表同步滚动到选中项（等 DOM 应用 .active 后再定位）
  nextTick(scrollRailToSelected)
}

// 让左侧角色库滚动到当前选中项（键盘翻动时保持选中项可见）。
// 用 getBoundingClientRect 差值计算，不受定位祖先影响；block=nearest 语义：
// 选中项在视口内就不动，只在越界时滚动到可见位置，连续翻动不会跳动。
function scrollRailToSelected() {
  const rail = railListRef.value
  if (!rail) return
  const active = rail.querySelector('.rail-card.active')
  if (!active) return
  const rTop = rail.getBoundingClientRect().top
  const rBottom = rail.getBoundingClientRect().bottom
  const eTop = active.getBoundingClientRect().top
  const eBottom = active.getBoundingClientRect().bottom
  if (eTop < rTop) {
    rail.scrollTop += eTop - rTop
  } else if (eBottom > rBottom) {
    rail.scrollTop += eBottom - rBottom
  }
}

async function batchDownload() {
  if (!selectedSet.value.size) return
  warmAudio()
  const targets = []
  if (skinMode.value) {
    for (const item of filteredSkins.value) {
      if (!selectedSet.value.has(item.skin.key)) continue
      const sk = item.skin
      if (sk.status === 'remote' && canDownload(sk)) {
        targets.push({ ship: item.ship.name, bundle: sk.bundle, name: sk.name })
      }
    }
  } else {
    for (const ship of ships.value) {
      if (!selectedSet.value.has(ship.id)) continue
      for (const sk of ship.skins) {
        if (sk.status === 'remote' && canDownload(sk)) {
          targets.push({ ship: ship.name, bundle: sk.bundle, name: sk.name })
        }
      }
    }
  }
  if (!targets.length) {
    showMsg(skinMode.value ? '所选皮肤没有可下载的资源' : '所选角色没有可下载的动态皮肤')
    return
  }
  startDl(`批量下载（${targets.length} 个皮肤）`, targets.length)
  batchDownloading.value = true
  batchDone.value = 0
  batchFailed.value = 0
  batchCancelled.value = 0
  batchTotal.value = targets.length
  const res = await runPoolWithRetry(targets, getConcurrency(), ({ done, failed, cancelled }) => {
    batchDone.value = done
    batchFailed.value = failed
    batchCancelled.value = cancelled
    dlProgress.done = done
    dlProgress.failed = failed
    dlProgress.cancelled = cancelled
  }, downloadBatchId.value)
  batchDownloading.value = false
  finishDl()
  ships.value = await bridge.listShips()
  clearSelection()
  if (res.done > 0) playChime()
  if (res.cancelled) {
    showMsg(
      `已取消：完成 ${res.done} 个，失败 ${res.failed} 个，取消 ${res.cancelledCount || 0} 个，未下载 ${Math.max(
        0,
        batchTotal.value - res.done - res.failed - (res.cancelledCount || 0),
      )} 个`,
    )
  } else {
    showMsg(res.failed
      ? `批量下载完成：${res.done} 成功，${res.failed} 失败（已自动重试一轮）`
      : `✓ 批量下载完成（${batchTotal.value} 个皮肤）`)
  }
}

function onSpineAnims(names) {
  animOptions.value = names.map((n) => ({ label: n, value: n }))
  if (!animation.value || !names.includes(animation.value)) {
    animation.value = names.find((n) => /^idle$/i.test(n)) || names[0] || ''
  }
}

const animIndex = computed(() => {
  const i = animOptions.value.findIndex((o) => o.value === animation.value)
  return i >= 0 ? i : 0
})

function stepAnim(dir) {
  const n = animOptions.value.length
  if (!n) return
  const next = (animIndex.value + dir + n) % n
  animation.value = animOptions.value[next].value
}

function onEngineError(msg) {
  console.error('[preview]', msg)
  showMsg(`✗ 预览引擎加载失败：${msg}`)
}

async function toggleFullscreen() {
  fullscreen.value = !fullscreen.value
  try {
    if (fullscreen.value) {
      await document.documentElement.requestFullscreen?.()
    } else {
      await document.exitFullscreen?.()
    }
  } catch (e) {
    // 浏览器/WebView 不支持时仅用 CSS 全屏
  }
}

// 以浏览器实际全屏状态为准同步 UI（用户按 Esc / 系统手势退出全屏时，状态不脱节）
function onFullscreenChange() {
  fullscreen.value = !!document.fullscreenElement
}

function onKeydown(e) {
  if (e.key === 'Escape' && fullscreen.value) {
    fullscreen.value = false
    return
  }
  const t = e.target
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return
  if (t && t.closest && t.closest('.n-select')) return
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    if (animOptions.value.length) {
      e.preventDefault()
      stepAnim(e.key === 'ArrowLeft' ? -1 : 1)
    }
    return
  }
  // 上下键：切换左侧列表选中项（角色/皮肤），保持选中项滚动可见。
  // 注意：不在此处改缩放——不同皮肤显示大小由取景统一（方案 B），切换角色不会“缩放跳变”。
  if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return
  if (fullscreen.value) return
  e.preventDefault()
  railStep(e.key === 'ArrowDown' ? 1 : -1)
}

async function doExport() {
  const skin = currentSkin.value
  if (!skin) return
  exporting.value = true
  exportDone.value = false
  exportResult.value = null
  try {
    exportResult.value = await bridge.exportWallpaper(skin.ship, skin.bundle, skin.name, {
      bg: bgStyle.value,
      bgColor: bgStyle.value === 'solid' ? solidColor.value || undefined : undefined,
      bgImage: bgStyle.value === 'image' ? selectedBgImage.value || undefined : undefined,
      scale: scale.value,
      bgScale: bgScale.value,
      offsetX: offsetX.value,
      offsetY: offsetY.value,
      charOffsetX: charOffsetX.value,
      charOffsetY: charOffsetY.value,
      bgOffsetX: bgOffsetX.value,
      bgOffsetY: bgOffsetY.value,
      alignment: alignment.value,
      animation: animation.value,
      interaction: enableInteraction.value,
      pose: currentPose.value,
    })
  } catch (e) {
    exportResult.value = { ok: false, error: e.message || '导出失败' }
  } finally {
    exporting.value = false
    exportDone.value = true
    clearTimeout(exportTimer)
    exportTimer = setTimeout(() => {
      exportDone.value = false
    }, 8000)
  }
}

async function doApply() {
  const skin = currentSkin.value
  if (!skin) return
  applying.value = true
  applyDone.value = false
  applyResult.value = null
  try {
    applyResult.value = await bridge.applyWallpaper(skin.ship, skin.bundle, skin.name, {
      bg: bgStyle.value,
      bgColor: bgStyle.value === 'solid' ? solidColor.value || undefined : undefined,
      bgImage: bgStyle.value === 'image' ? selectedBgImage.value || undefined : undefined,
      scale: scale.value,
      bgScale: bgScale.value,
      offsetX: offsetX.value,
      offsetY: offsetY.value,
      charOffsetX: charOffsetX.value,
      charOffsetY: charOffsetY.value,
      bgOffsetX: bgOffsetX.value,
      bgOffsetY: bgOffsetY.value,
      alignment: alignment.value,
      animation: animation.value,
      interaction: enableInteraction.value,
      pose: currentPose.value,
    })
  } catch (e) {
    applyResult.value = { ok: false, error: e.message || '导出并应用失败' }
  } finally {
    applying.value = false
    applyDone.value = true
    clearTimeout(applyTimer)
    applyTimer = setTimeout(() => {
      applyDone.value = false
    }, 8000)
  }
}

async function downloadCurrent() {
  const skin = currentSkin.value
  if (!skin) return
  warmAudio()
  startDl(`下载：${skin.name}`, 1)
  downloading.value = true
  downloadMsg.value = ''
  try {
    const res = await bridge.downloadSkin(skin.ship, skin.bundle, skin.name, downloadBatchId.value)
    if (res && res.cancelled) {
      dlProgress.cancelled = 1
      showMsg('已取消下载')
    } else if (res && res.ok) {
      dlProgress.done = 1
      playChime()
      showMsg('✓ 下载完成，已自动提取入库')
      ships.value = await bridge.listShips()
    } else {
      dlProgress.failed = 1
      showMsg(`✗ 下载失败：${(res && res.error) || '未知错误'}`)
    }
  } catch (e) {
    showMsg(downloadCancelled ? '已取消下载' : `✗ 下载异常：${e.message}`)
  } finally {
    downloading.value = false
    finishDl()
  }
}

async function downloadAll() {
  const ship = selectedShip.value
  if (!ship) return
  warmAudio()
  const targets = ship.skins.filter((sk) => sk.status === 'remote' && canDownload(sk))
  if (!targets.length) {
    showMsg('该角色没有可下载的资源')
    return
  }
  startDl(`下载全部：${ship.name}`, targets.length)
  allDownloading.value = true
  allDone.value = 0
  allFailed.value = 0
  allTotal.value = targets.length
  const res = await runPoolWithRetry(targets, getConcurrency(), ({ done, failed, cancelled }) => {
    allDone.value = done
    allFailed.value = failed
    dlProgress.done = done
    dlProgress.failed = failed
    dlProgress.cancelled = cancelled
  }, downloadBatchId.value)
  allDownloading.value = false
  finishDl()
  ships.value = await bridge.listShips()
  if (res.done > 0) playChime()
  if (res.cancelled) {
    showMsg(`已取消：完成 ${res.done} 个，失败 ${res.failed} 个，取消 ${res.cancelledCount || 0} 个`)
  } else {
    showMsg(res.failed
      ? `下载全部完成：${res.done} 成功，${res.failed} 失败（已自动重试一轮）`
      : `✓ 已下载全部 ${allTotal.value} 个资源`)
  }
}

onMounted(async () => {
  const wrap = stageWrapRef.value
  if (wrap) {
    fitStage()
    stageRO = new ResizeObserver(fitStage)
    stageRO.observe(wrap)
  }
  loadFavs()
  try {
    avatars.value = await (await fetch(metadataUrl('avatars.json'), { cache: 'no-store' })).json()
    avatarsStamp.value = Date.now()
    avatarFailed.value = new Set()
  } catch (e) {
    avatars.value = {}
  }
  try {
    ships.value = await bridge.listShips()
  } catch (e) {
    showMsg(`✗ 加载资源库失败：${e.message}`)
    ships.value = []
  }
  loading.value = false
  const first =
    ships.value.find((s) => s.skins.some((k) => k.status === 'downloaded')) || ships.value[0]
  if (first) selectShip(first)
  window.addEventListener('keydown', onKeydown)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

// keep-alive 缓存后从设置等页面返回时触发：刷新数据但保留当前选中的角色/皮肤
onActivated(async () => {
  try {
    const fresh = await bridge.listShips()
    if (fresh && fresh.length) {
      ships.value = fresh
      if (!selectedShip.value) selectShip(fresh[0])
    }
  } catch (e) {
    /* 忽略刷新失败，保留现有数据 */
  }
  try {
    avatars.value = await (await fetch(metadataUrl('avatars.json'), { cache: 'no-store' })).json()
    // 头像映射刷新：更新版本戳（图片 URL 变化强制重载），并清失败集合让占位角色重试
    avatarsStamp.value = Date.now()
    avatarFailed.value = new Set()
  } catch (e) {
    /* 头像缺失时回退首字 */
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  clearTimeout(msgTimer)
  clearTimeout(exportTimer)
  clearTimeout(applyTimer)
  clearTimeout(searchTimer)
  if (stageRO) stageRO.disconnect()
})
</script>

<style scoped>
.main-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.main-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--line);
  background: rgba(250, 248, 245, 0.86);
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}

.main-title h1 {
  margin: 0;
  font-family: var(--font-serif);
  font-weight: 300;
  letter-spacing: 2px;
  font-size: 20px;
}

.main-title span {
  color: var(--muted);
  font-size: 12px;
  margin-left: 10px;
}

.main-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* ---- 左侧角色库 ---- */
.ship-rail {
  width: 300px;
  flex-shrink: 0;
  border-right: 1px solid var(--line);
  background: rgba(250, 248, 245, 0.8);
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 10px;
}

.rail-pills {
  display: flex;
  gap: 6px;
}

.rail-tools {
  display: flex;
  gap: 6px;
}

.filter-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.filter-field label {
  color: var(--muted);
  font-size: 12px;
}

.clear-filter-btn {
  grid-column: span 2;
  padding: 7px 0;
}

.rail-tool {
  flex: 1;
  text-align: center;
  padding: 6px 0;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.7);
  color: var(--muted);
  cursor: pointer;
  font-size: 12px;
  font-weight: 300;
  transition: all 0.3s ease-out;
  user-select: none;
}

.rail-tool:hover {
  color: var(--blue);
  border-color: rgba(74, 111, 165, 0.5);
  background: #fff;
}

.rail-tool.active {
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(133, 205, 202, 0.14));
  border-color: rgba(74, 111, 165, 0.55);
  color: #3a5a88;
  box-shadow: 0 4px 16px rgba(74, 111, 165, 0.14);
}

.type-pill {
  flex: 1;
  text-align: center;
  padding: 7px 0;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.7);
  color: var(--muted);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s ease-out;
  user-select: none;
}

.type-pill:hover {
  color: var(--blue);
  border-color: rgba(74, 111, 165, 0.5);
  background: #fff;
}

.type-pill.active {
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(133, 205, 202, 0.14));
  border-color: rgba(74, 111, 165, 0.55);
  color: #3a5a88;
  box-shadow: 0 4px 16px rgba(74, 111, 165, 0.14);
}

.rail-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.rail-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 16px;
  border: 1px solid transparent;
  background: rgba(250, 248, 245, 0.9);
  cursor: pointer;
  transition: all 0.3s ease-out;
}

.rail-card:hover {
  border-color: rgba(74, 111, 165, 0.3);
  transform: scale(1.015);
}

.rail-card.active {
  border-color: rgba(74, 111, 165, 0.5);
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(180, 120, 140, 0.12));
  box-shadow: var(--shadow-soft);
}

.rail-avatar {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  overflow: hidden;
}

.rail-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.rail-char {
  font-family: var(--font-serif);
  font-size: 16px;
  color: rgba(58, 58, 58, 0.8);
}

.rail-info {
  min-width: 0;
  flex: 1;
}

.rail-name {
  font-family: var(--font-serif);
  font-size: 14px;
  letter-spacing: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.rail-skin {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.rail-meta {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.rail-star {
  position: absolute;
  top: 6px;
  right: 8px;
  z-index: 2;
  color: var(--gold);
  cursor: pointer;
  font-size: 14px;
  opacity: 0.6;
  transition: all 0.3s ease-out;
}

.rail-star:hover {
  opacity: 1;
  transform: scale(1.15);
}

.rail-star.fav {
  opacity: 1;
}

.rail-check {
  position: absolute;
  bottom: 6px;
  right: 8px;
  z-index: 2;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.7);
  display: grid;
  place-items: center;
  font-size: 11px;
  color: transparent;
}

.rail-check.on {
  background: rgba(74, 111, 165, 0.85);
  color: #fff;
  border-color: transparent;
}

/* ---- 中心预览区 ---- */
.preview-zone {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.stage-wrap {
  flex: 1;
  min-height: 0;
  display: grid;
  place-items: center;
  overflow: hidden;
}

.preview-stage {
  position: relative;
  overflow: hidden;
  display: grid;
  place-items: center;
  border-radius: 14px;
  box-shadow: var(--shadow-hover);
}

.stage-info {
  position: absolute;
  top: 14px;
  left: 16px;
  z-index: 4;
  display: flex;
  align-items: baseline;
  gap: 8px;
  pointer-events: none;
  text-shadow: 0 1px 8px rgba(0, 0, 0, 0.45);
}

.stage-info-name {
  font-family: var(--font-serif);
  font-size: 20px;
  letter-spacing: 2px;
  color: rgba(250, 248, 245, 0.96);
}

.stage-info-skin {
  font-size: 13px;
  color: rgba(240, 235, 227, 0.75);
}

/* ---- L2D 版式调节浮窗（极致小巧、半透明毛玻璃胶囊） ---- */
.l2d-panel-a {
  position: absolute;
  right: 58px;
  top: 14px;
  z-index: 6;
  width: auto;
  background: rgba(14, 20, 32, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  padding: 3px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: opacity 0.2s ease, transform 0.2s ease;
  opacity: 0.85;
}

.l2d-panel-a:hover {
  opacity: 1;
  transform: translateY(-1px);
}

.adjust-seg {
  position: relative;
  display: flex;
  align-items: center;
  gap: 2px;
  border-radius: 999px;
  background: transparent;
  padding: 0;
}

.adjust-seg-thumb {
  position: absolute;
  top: 0;
  left: 0;
  width: 44px;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.92), rgba(133, 205, 202, 0.85));
  box-shadow: 0 2px 8px rgba(74, 111, 165, 0.5);
  transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}

.adjust-seg.at-stage .adjust-seg-thumb {
  transform: translateX(0);
}

.adjust-seg.at-char .adjust-seg-thumb {
  transform: translateX(46px);
}

.adjust-seg.at-bg .adjust-seg-thumb {
  transform: translateX(92px);
}

.adjust-seg-item {
  position: relative;
  width: 44px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  letter-spacing: 1px;
  font-family: var(--font-sans);
  color: rgba(240, 235, 227, 0.72);
  cursor: pointer;
  user-select: none;
  transition: color 0.2s ease;
  border: none;
  background: transparent;
  padding: 0;
}

.adjust-seg-item:hover {
  color: #fff;
}

.adjust-seg-item.active {
  color: #fff;
  font-weight: 600;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}

/* 拖动/滚轮调节对象切换（画面/人物/背景）：与"拖拽/互动"同款滑块式分段视觉，
   三段等分面板宽、按钮高度与"拖拽/互动"一致（32px），段间 6px 间距，
   滑块宽度按 (100%-12px)/3 计算、位移按「滑块宽 + 6px」步进 */
.adjust-row {
  flex-direction: column;
  align-items: stretch;
  margin-bottom: 2px;
}

.adjust-seg {
  position: relative;
  display: flex;
  width: 100%;
  gap: 6px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 12px;
  padding: 3px;
}

.adjust-seg-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: calc((100% - 12px) / 3);
  height: calc(100% - 6px);
  border-radius: 10px;
  background: linear-gradient(120deg, rgba(74, 111, 165, 0.9), rgba(133, 205, 202, 0.85));
  box-shadow: 0 4px 14px rgba(74, 111, 165, 0.45);
  transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.adjust-seg.at-char .adjust-seg-thumb {
  transform: translateX(calc(100% + 6px));
}

.adjust-seg.at-bg .adjust-seg-thumb {
  transform: translateX(calc(200% + 12px));
}

.adjust-seg-item {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 7px 0;
  font-size: 12.5px;
  letter-spacing: 2px;
  font-family: var(--font-sans);
  color: rgba(255, 255, 255, 0.78);
  cursor: pointer;
  user-select: none;
  transition: color 0.25s ease;
  border: none;
  background: transparent;
}

.adjust-seg-item:hover {
  color: #fff;
}

.adjust-seg-item.active {
  color: #fff;
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.35);
}

.l2d-seg-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: calc(50% - 3px);
  height: calc(100% - 6px);
  border-radius: 10px;
  background: linear-gradient(120deg, rgba(74, 111, 165, 0.9), rgba(133, 205, 202, 0.85));
  box-shadow: 0 4px 14px rgba(74, 111, 165, 0.45);
  transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.l2d-seg.on-interact .l2d-seg-thumb {
  transform: translateX(100%);
}

.l2d-seg-item {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 0;
  font-size: 12.5px;
  letter-spacing: 2px;
  font-family: var(--font-sans);
  color: rgba(255, 255, 255, 0.78);
  cursor: pointer;
  user-select: none;
  transition: color 0.25s ease;
  border: none;
  background: transparent;
}

.l2d-seg-item.active {
  color: #fff;
  font-weight: 500;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}

.l2d-seg-item svg {
  width: 15px;
  height: 15px;
  flex: none;
}

/* 开关行 */
.l2d-switch-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 4px;
  border-radius: 12px;
  transition: background 0.2s ease;
}

.l2d-switch-row:hover {
  background: rgba(255, 255, 255, 0.05);
}

.l2d-switch-ico {
  width: 26px;
  height: 26px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.07);
  color: rgba(240, 235, 227, 0.85);
}

.l2d-switch-ico.on {
  color: var(--gold);
  background: rgba(201, 168, 76, 0.22);
}

.l2d-switch-txt {
  flex: 1;
  font-size: 12.5px;
  letter-spacing: 1px;
  color: rgba(240, 235, 227, 0.9);
}

.l2d-switch-txt small {
  display: block;
  font-size: 10.5px;
  color: rgba(240, 235, 227, 0.5);
  letter-spacing: 0.5px;
  margin-top: 1px;
}

.l2d-switch {
  position: relative;
  width: 38px;
  height: 22px;
  flex: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  cursor: pointer;
  transition: background 0.25s ease;
}

.l2d-switch::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
  transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.l2d-switch.on {
  background: linear-gradient(120deg, rgba(201, 168, 76, 0.9), rgba(180, 120, 140, 0.85));
}

.l2d-switch.on::after {
  transform: translateX(16px);
}

/* 台词框 */
.l2d-subtitle-a {
  position: relative;
  margin-top: 9px;
  padding: 12px 14px 11px 18px;
  max-height: 120px;
  overflow-y: auto;
  box-sizing: border-box;
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.92);
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
}

.l2d-subtitle-a::before {
  content: '“';
  position: absolute;
  left: 6px;
  top: 2px;
  font-family: var(--font-serif);
  font-size: 26px;
  line-height: 1;
  color: rgba(201, 168, 76, 0.75);
}

.l2d-subtitle-a-who {
  display: block;
  font-size: 10.5px;
  letter-spacing: 2px;
  color: var(--gold);
  margin-bottom: 3px;
}

.l2d-subtitle-a.empty {
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
}

.l2d-subtitle-a.empty::before {
  display: none;
}

.stage-fullscreen-btn {
  position: absolute;
  top: 14px;
  right: 16px;
  z-index: 5;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(10, 14, 24, 0.42);
  backdrop-filter: blur(6px);
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease-out;
}

.stage-fullscreen-btn:hover {
  background: rgba(10, 14, 24, 0.62);
  transform: scale(1.08);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
}

/* ---- 皮肤切换条 ---- */
.skin-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-top: 1px solid var(--line);
  background: rgba(250, 248, 245, 0.9);
}

.skin-strip {
  flex: 1;
  min-width: 0;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.skin-status {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dl-ok {
  color: #6b9d7a;
  font-size: 13px;
}

/* ---- 右侧控制面板 ---- */
.control-panel {
  width: 300px;
  flex-shrink: 0;
  border-left: 1px solid var(--line);
  background: rgba(250, 248, 245, 0.86);
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  overflow-y: auto;
}

.panel-card {
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px;
  box-shadow: var(--shadow-soft);
}

.panel-title {
  color: var(--muted);
  font-size: 12px;
  letter-spacing: 2px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px dashed rgba(120, 120, 120, 0.22);
}

/* 导出面板内的调节分组（人物调节/背景调节）小标题 */
.panel-group {
  padding-top: 2px;
}

.panel-group + .panel-group {
  margin-top: 14px;
}

.panel-group-title {
  color: rgba(133, 205, 202, 0.9);
  font-size: 11.5px;
  letter-spacing: 2px;
  margin-bottom: 8px;
  padding-left: 8px;
  border-left: 2px solid rgba(133, 205, 202, 0.55);
  line-height: 1.2;
}

.export-actions .wc-btn + .wc-btn {
  margin-top: 14px;
}

.dl-btn {
  padding: 6px 16px;
  font-size: 13px;
}

.export-alert {
  margin-top: 10px;
  font-size: 12px;
}

.panel-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.panel-field:last-child {
  margin-bottom: 0;
}

.panel-field label {
  color: var(--muted);
  font-size: 12px;
}

.panel-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.anim-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 8px;
}

.anim-nav-btn {
  padding: 4px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.4;
  min-width: 36px;
}

.anim-nav-label {
  color: var(--muted);
  font-size: 12px;
  min-width: 46px;
  text-align: center;
}

.panel-tip {
  color: #b07a3a;
  font-size: 12px;
  margin: 8px 0 0;
  line-height: 1.6;
}

.panel-nav {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed rgba(120, 120, 120, 0.22);
}

.panel-nav-btn {
  flex: 1;
  padding: 7px 10px;
  border-radius: 12px;
}

.panel-nav-btn.active {
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(133, 205, 202, 0.14));
  border-color: rgba(74, 111, 165, 0.55);
  color: #3a5a88;
}

.bar-dim {
  color: var(--muted);
  font-size: 12px;
}

/* 偏移滑块行：滑块 + 实时数值并排，数值右对齐等宽数字，0 弱化 */
.offset-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.reset-bgscale {
  font-size: 12px;
  padding: 2px 10px;
  white-space: nowrap;
}
.offset-row .n-slider {
  flex: 1;
  min-width: 0;
}
.bar-value {
  min-width: 42px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.3px;
  color: var(--blue);
}
.bar-value.zero {
  color: var(--muted);
  font-weight: 400;
}

/* WE 预设导入 */
.preset-import-btn {
  width: 100%;
  justify-content: center;
  font-size: 13px;
  padding: 7px 12px;
  border-style: dashed;
}
.preset-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

.download-msg {
  position: fixed;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 20;
  padding: 10px 20px;
  border-radius: 999px;
  background: rgba(250, 248, 245, 0.95);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-soft);
  font-size: 13px;
  color: var(--ink);
}

.batch-bar {
  position: fixed;
  bottom: 70px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  border-radius: 999px;
  background: rgba(250, 248, 245, 0.96);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-hover);
  font-size: 13px;
  color: var(--ink);
}

.batch-progress {
  width: 140px;
  height: 6px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.batch-progress-bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #4a6fa5, #b4788c);
  transition: width 0.2s ease-out;
}

.batch-progress-text {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}

.zoom-hint {
  position: absolute;
  right: 16px;
  bottom: 14px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 12px;
  background: rgba(0, 0, 0, 0.35);
  padding: 3px 10px;
  border-radius: 999px;
}

.preview-placeholder {
  position: relative;
  text-align: center;
  user-select: none;
}

.preview-halo {
  width: 260px;
  height: 260px;
  margin: 0 auto 18px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(74, 111, 165, 0.35), rgba(180, 120, 140, 0.18) 45%, transparent 70%);
  filter: blur(2px);
  animation: halo-float 5s ease-in-out infinite;
}

@keyframes halo-float {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-16px) scale(1.06); }
}

.preview-title {
  font-family: var(--font-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 5px;
  margin-bottom: 10px;
  color: rgba(250, 248, 245, 0.96);
  text-shadow: 0 2px 16px rgba(0, 0, 0, 0.4);
}

.preview-sub {
  color: rgba(240, 235, 227, 0.7);
  font-size: 13px;
}

.export-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.export-form label {
  color: var(--muted);
  font-size: 12px;
  margin-top: 4px;
}

/* 皮肤收藏星标（皮肤切换条右侧，始终可点击） */
.skin-fav-btn {
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.14), rgba(133, 205, 202, 0.18));
  border: 1px solid rgba(74, 111, 165, 0.35);
  color: rgba(74, 111, 165, 0.75);
  font-size: 15px;
  cursor: pointer;
  display: inline-grid;
  place-items: center;
  transition: transform 0.25s ease-out, color 0.25s ease-out, box-shadow 0.25s ease-out;
}
.skin-fav-btn:hover {
  transform: scale(1.12);
  box-shadow: 0 4px 14px rgba(74, 111, 165, 0.25);
}
.skin-fav-btn.on {
  background: linear-gradient(135deg, rgba(201, 168, 76, 0.9), rgba(240, 200, 90, 0.95));
  border-color: rgba(201, 168, 76, 0.65);
  color: #fff;
  box-shadow: 0 4px 16px rgba(201, 168, 76, 0.4);
}

/* 批量操作栏内的渐变按钮 */
.batch-bar .batch-btn {
  padding: 6px 16px;
  font-size: 12px;
}

/* 右下角下载进度条 */
.dl-progress-card {
  position: fixed;
  right: 0;
  bottom: 24px;
  z-index: 30;
  width: 300px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(250, 248, 245, 0.97);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-hover);
  backdrop-filter: blur(8px);
}
.dl-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.dl-progress-label {
  font-size: 13px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dl-progress-cancel {
  padding: 4px 14px;
  font-size: 12px;
  flex-shrink: 0;
}
.dl-progress-track {
  height: 8px;
  border-radius: 999px;
  background: rgba(74, 111, 165, 0.12);
  overflow: hidden;
}
.dl-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #4a6fa5, #85cdca);
  transition: width 0.3s ease-out;
}
.dl-progress-meta {
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}

.dl-progress-stage {
  margin-top: 6px;
  font-size: 12px;
  color: var(--blue);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 导出可切换动画多选：选中的标签改成圆润渐变淡色药丸 */
.anim-multi :deep(.n-base-selection-tag-wrapper .n-tag) {
  border-radius: 999px !important;
  border: 1px solid rgba(74, 111, 165, 0.28) !important;
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.14), rgba(133, 205, 202, 0.2)) !important;
  color: #3f5f8f;
}
.anim-multi :deep(.n-base-selection-tag-wrapper .n-tag .n-tag__close) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0 2px 0 4px;
  padding: 0;
  font-size: 14px;
  color: rgba(63, 95, 143, 0.7);
}

/* 全屏模式 */
.main-view.is-fullscreen .preview-zone {
  width: 100%;
}

/* 官方背景与选择器布局优化 */
.bg-select-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}
.bg-select-main {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.bg-current-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.035);
  border: 1px solid rgba(120, 140, 170, 0.2);
  border-radius: 6px;
  width: 100%;
  box-sizing: border-box;
}
.bg-current-name {
  font-size: 11px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.bg-change-btn {
  padding: 3px 10px;
  font-size: 11px;
  white-space: nowrap;
  flex-shrink: 0;
  border-radius: 5px;
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(133, 205, 202, 0.22));
  border: 1px solid rgba(74, 111, 165, 0.4);
  color: var(--text);
  cursor: pointer;
  transition: all 0.2s ease;
}
.bg-change-btn:hover {
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.28), rgba(133, 205, 202, 0.38));
}
/* 扩图合成工作流（导出当前背景 → 外部扩图 → 导入） */
.bg-outpaint-bar {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  background: linear-gradient(135deg, rgba(201, 168, 76, 0.1), rgba(74, 111, 165, 0.08));
  border: 1px dashed rgba(201, 168, 76, 0.5);
  border-radius: 8px;
  width: 100%;
  box-sizing: border-box;
}
.bg-outpaint-steps {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 11px;
  line-height: 1.4;
}
.bg-outpaint-title {
  font-weight: 600;
  color: #8a6d1f;
  flex-shrink: 0;
}
.bg-outpaint-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.bg-outpaint-actions .wc-btn {
  padding: 3px 8px;
  font-size: 11px;
  white-space: nowrap;
}
/* output / input 目录按钮：比操作按钮更轻，避免与「导出/导入」混淆 */
.bg-outpaint-folder {
  flex-shrink: 0;
  padding: 3px 7px;
  background: rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(120, 140, 170, 0.3);
  color: var(--muted);
}
.bg-outpaint-folder:hover {
  background: rgba(74, 111, 165, 0.14);
  color: var(--text);
}
.bg-upscale-card {
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(74, 111, 165, 0.22);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  box-sizing: border-box;
}
.bg-upscale-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.bg-adv-toggle-btn {
  border: none;
  background: transparent;
  font-size: 11px;
  color: var(--muted);
  cursor: pointer;
  padding: 1px 4px;
  border-radius: 4px;
  transition: all 0.2s ease;
}
.bg-adv-toggle-btn:hover {
  color: var(--blue, #4a6fa5);
  background: rgba(74, 111, 165, 0.1);
}
.bg-adv-toggle-btn.on {
  color: var(--blue, #4a6fa5);
  font-weight: 500;
}
.upscale-adv-drawer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.035);
  border: 1px dashed rgba(120, 140, 170, 0.25);
  border-radius: 6px;
  margin-top: 2px;
}
.adv-param-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.adv-label {
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
}
.bg-upscale-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--blue, #4a6fa5);
}
.bg-scale-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(34, 197, 94, 0.15);
  color: #15803d;
  font-weight: 500;
}
.bg-scale-tag.ml-2 {
  margin-left: 6px;
}
.bg-scale-tag.custom-tag {
  background: rgba(201, 168, 76, 0.22);
  color: #8a6d1f;
}
.bg-upscale-inputs {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}
.upscale-select-row {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.upscale-actions-row {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.bg-upscale-submit-btn {
  flex: 1;
  padding: 6px 0;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.5px;
  border-radius: 6px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(74, 111, 165, 0.2);
}
.bg-upscale-submit-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: none;
}
.text-btn {
  border: none;
  background: transparent;
  color: var(--blue, #4a6fa5);
  font-size: 11px;
  cursor: pointer;
  padding: 0;
}
.text-btn:hover {
  text-decoration: underline;
}
.bg-modal-upscale-box {
  display: flex;
  align-items: center;
  gap: 8px;
}
.open-bg-folder-btn {
  padding: 4px 12px;
  font-size: 11.5px;
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.16), rgba(133, 205, 202, 0.22));
  border: 1px solid rgba(74, 111, 165, 0.4);
  color: var(--text);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}
.open-bg-folder-btn:hover {
  background: linear-gradient(135deg, rgba(74, 111, 165, 0.28), rgba(133, 205, 202, 0.38));
  box-shadow: 0 2px 8px rgba(74, 111, 165, 0.2);
}
.bg-selector-modal {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 68vh;
}
.bg-selector-toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bg-selector-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.bg-selector-dir-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.bg-cat-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.bg-cat-pill {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 999px;
  border: 1px solid rgba(120, 140, 170, 0.25);
  background: rgba(255, 255, 255, 0.6);
  color: var(--text);
  cursor: pointer;
  transition: all 0.2s ease;
}
.bg-cat-pill:hover {
  border-color: rgba(74, 111, 165, 0.5);
  background: rgba(74, 111, 165, 0.08);
}
.bg-cat-pill.active {
  background: linear-gradient(135deg, #4a6fa5, #85cdca);
  color: #fff;
  border-color: transparent;
  font-weight: 500;
}
.bg-cat-pill.rec-pill {
  border-color: rgba(201, 168, 76, 0.5);
  background: rgba(201, 168, 76, 0.12);
}
.bg-cat-pill.rec-pill.active {
  background: linear-gradient(135deg, #c9a84c, #f59e0b);
  color: #fff;
}
.bg-rec-section {
  background: rgba(201, 168, 76, 0.06);
  border: 1px dashed rgba(201, 168, 76, 0.35);
  border-radius: 8px;
  padding: 8px 10px;
}
.bg-rec-title {
  font-size: 12px;
  font-weight: 600;
  color: #9a7c2e;
  margin-bottom: 6px;
}
.bg-rec-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
}
.bg-grid-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}
.bg-empty-tip {
  text-align: center;
  padding: 40px 0;
  color: var(--muted);
  font-size: 13px;
}
.bg-more-tip {
  text-align: center;
  padding: 12px 0;
  color: var(--muted);
  font-size: 11px;
}
.bg-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
}
.bg-card {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  background: rgba(0, 0, 0, 0.05);
  cursor: pointer;
  aspect-ratio: 16 / 9;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.bg-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.15);
  border-color: rgba(74, 111, 165, 0.6);
}
.bg-card.selected {
  border-color: #4a6fa5;
  box-shadow: 0 0 0 2px rgba(74, 111, 165, 0.35);
}
.bg-card.rec-card {
  aspect-ratio: 16 / 9;
}
/* 自定义 / 扩图背景标识与删除（二次确认） */
.bg-card-badge {
  position: absolute;
  top: 4px;
  left: 4px;
  z-index: 2;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  background: rgba(201, 168, 76, 0.9);
  pointer-events: none;
}
.bg-card-del {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 2;
  padding: 1px 6px;
  border-radius: 4px;
  border: none;
  font-size: 10px;
  line-height: 1.6;
  color: #fff;
  background: rgba(0, 0, 0, 0.45);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s ease, background 0.2s ease;
}
.bg-card:hover .bg-card-del {
  opacity: 1;
}
.bg-card-del.armed {
  opacity: 1;
  background: rgba(200, 60, 60, 0.92);
}
.bg-card-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.bg-card-info {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 4px 6px;
  background: linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.75));
  color: #fff;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
