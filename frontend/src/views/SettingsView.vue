<template>
  <div class="settings-layout">
    <header class="settings-topbar">
      <router-link to="/" class="settings-back-btn">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        返回
      </router-link>
      <h1 class="settings-title">设置</h1>
    </header>

    <main class="settings-main">
      <!-- 1. 模型配置 -->
      <section class="settings-card">
        <div class="section-header">
          <h2 class="settings-section-title">模型配置</h2>
          <p class="section-desc">连接到大语言模型服务，配置 API 地址、密钥和模型参数</p>
        </div>
        <div class="settings-field">
          <label>API URL</label>
          <input v-model="settingsStore.apiUrl" type="text" placeholder="https://api.deepseek.com/v1" @blur="handleApiBlur">
        </div>
        <div class="settings-field">
          <label>API Key</label>
          <input v-model="settingsStore.apiKey" type="password" placeholder="sk-..." autocomplete="off" @blur="handleApiBlur">
        </div>
        <div class="settings-field">
          <label>模型</label>
          <div class="model-select-wrapper">
            <select v-if="settingsStore.models.length > 0" v-model="settingsStore.selectedModel" class="model-select">
              <option v-for="m in settingsStore.models" :key="m" :value="m">{{ m }}</option>
            </select>
            <input v-else v-model="settingsStore.selectedModel" type="text" placeholder="deepseek-chat">
          </div>
        </div>
        <div class="settings-field-row">
          <span>深度思考</span>
          <button class="toggle-btn" :class="{ active: settingsStore.thinkingEnabled }" @click="settingsStore.toggleThinking()">
            <span class="toggle-knob"></span>
          </button>
        </div>
      </section>

      <!-- 2. 对话行为 -->
      <section class="settings-card">
        <div class="section-header">
          <h2 class="settings-section-title">对话行为</h2>
          <p class="section-desc">控制 AI 的回答方式，包括反思改进和文献检索增强</p>
        </div>
        <div class="settings-field-row">
          <div>
            <span>反思模式</span>
            <div class="field-hint">生成回答后自动反思改进</div>
          </div>
          <button class="toggle-btn" :class="{ active: settingsStore.reflectionEnabled }" @click="settingsStore.reflectionEnabled = !settingsStore.reflectionEnabled">
            <span class="toggle-knob"></span>
          </button>
        </div>
        <div class="settings-field-row">
          <div>
            <span>文献引用</span>
            <div class="field-hint">基于文献库检索增强回答</div>
          </div>
          <button class="toggle-btn" :class="{ active: settingsStore.ragEnabled }" @click="settingsStore.ragEnabled = !settingsStore.ragEnabled">
            <span class="toggle-knob"></span>
          </button>
        </div>
      </section>

      <!-- 3. 主题与界面 -->
      <section class="settings-card">
        <div class="section-header">
          <h2 class="settings-section-title">主题与界面</h2>
          <p class="section-desc">调整外观主题和字体大小，让界面更舒适</p>
        </div>
        <div class="settings-field">
          <label>外观主题</label>
          <div class="theme-switcher">
            <button class="theme-option" :class="{ active: theme.mode.value === 'system' }" @click="theme.setMode('system')">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
              随系统
            </button>
            <button class="theme-option" :class="{ active: theme.mode.value === 'light' }" @click="theme.setMode('light')">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
              浅色
            </button>
            <button class="theme-option" :class="{ active: theme.mode.value === 'dark' }" @click="theme.setMode('dark')">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
              深色
            </button>
          </div>
        </div>
        <div class="settings-field">
          <label>字体大小（{{ settingsStore.fontSize }}px）</label>
          <input type="range" :min="12" :max="20" :step="1" :value="settingsStore.fontSize" @input="settingsStore.fontSize = Number(($event.target as HTMLInputElement).value)" class="font-slider">
        </div>
      </section>

      <!-- 4. 存储管理 -->
      <section class="settings-card">
        <div class="section-header">
          <h2 class="settings-section-title">存储管理</h2>
          <p class="section-desc">查看本地存储用量，导出或清理缓存数据</p>
        </div>
        <div class="storage-usage">
          <span>本地存储用量</span>
          <span class="storage-value">{{ storageUsage }}</span>
        </div>
        <div class="storage-actions">
          <button class="storage-btn" @click="handleExport">导出数据</button>
          <button class="storage-btn storage-btn-danger" @click="handleClearCache">清理缓存</button>
        </div>
      </section>

      <!-- 5. 关于 -->
      <section class="settings-card">
        <div class="about-header">
          <span class="about-logo" v-html="logoSvg" @click="handleLogoClick" />
          <div v-if="easterEggActive" class="easter-overlay" @click="easterEggActive = false">
            <div class="easter-content">
              <div ref="easterContainer" class="easter-lottie"></div>
              <span class="easter-text">REJECT BALDNESS</span>
            </div>
          </div>
          <div class="about-info">
            <h2 class="settings-section-title">论文助手</h2>
            <p class="about-version">v0.1.0 · MVP</p>
          </div>
        </div>
        <div class="about-body">
          <p class="about-desc">基于 RAG 的学术写作助手，当前以 WPS 插件形态运行。</p>
          <div class="about-stack">
            <span class="about-tag" v-for="tag in techTags" :key="tag">{{ tag }}</span>
          </div>
          <div class="about-links">
            <span class="about-link-item">Vue 3 + TypeScript + Vite</span>
            <span class="about-link-divider">·</span>
            <span class="about-link-item">FastAPI + Pydantic</span>
            <span class="about-link-divider">·</span>
            <span class="about-link-item">ChromaDB</span>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useTheme } from '../composables/use-theme'
import logoSvg from '../assets/icons/ai-science-spark.svg?raw'
import easterEggData from '../assets/animations/easter-egg.json'

const settingsStore = useSettingsStore()
const theme = useTheme()

const storageUsage = ref('')

const techTags = ['RAG', 'BM25 + Dense', 'VLM', 'MinerU', 'DeepSeek', 'Qwen3-Embedding']

// easter egg: 连点 logo 5 次触发 Lottie 动画
const easterClickCount = ref(0)
const easterEggActive = ref(false)
const easterContainer = ref<HTMLElement | null>(null)
let easterTimer: ReturnType<typeof setTimeout> | null = null
let lottieAnim: { destroy: () => void } | null = null

function handleLogoClick() {
  easterClickCount.value++
  if (easterTimer) clearTimeout(easterTimer)
  easterTimer = setTimeout(() => { easterClickCount.value = 0 }, 1500)
  if (easterClickCount.value >= 5) {
    easterClickCount.value = 0
    easterEggActive.value = true
  }
}

watch(easterEggActive, async (active) => {
  if (!active) {
    lottieAnim?.destroy()
    lottieAnim = null
    return
  }
  await nextTick()
  if (!easterContainer.value) return
  const lottie = (await import('lottie-web')).default
  lottieAnim = lottie.loadAnimation({
    container: easterContainer.value,
    renderer: 'svg',
    loop: true,
    autoplay: true,
    animationData: easterEggData,
  })
})

onMounted(() => {
  storageUsage.value = settingsStore.estimateStorageUsage()
})

function handleApiBlur() {
  if (settingsStore.apiUrl && settingsStore.apiKey) {
    settingsStore.fetchModels()
  }
}

function handleExport() {
  const data = settingsStore.exportData()
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `paper-assistant-export-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function handleClearCache() {
  if (!confirm('确定清理缓存？将保留 API 配置和偏好设置。')) return
  settingsStore.clearCache()
  storageUsage.value = settingsStore.estimateStorageUsage()
}
</script>

<style scoped>
.settings-layout {
  height: 100%;
  background: var(--color-surface-base);
  overflow-y: auto;
  overflow-x: hidden;
}

.settings-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--color-surface-card);
  border-bottom: 1px solid var(--color-border-subtle);
}

.settings-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  text-decoration: none;
  transition: background 0.15s ease;
}

.settings-back-btn:hover {
  background: var(--color-surface-muted);
}

.settings-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.settings-main {
  max-width: 640px;
  margin: 0 auto;
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-card {
  padding: 20px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: 14px;
}

.settings-section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-header {
  margin-bottom: 14px;
}

.section-desc {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 4px;
  line-height: 1.4;
}

.settings-field {
  margin-bottom: 12px;
}

.settings-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.settings-field input[type="text"],
.settings-field input[type="password"] {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-primary);
  background: var(--color-surface-base);
  outline: none;
  transition: border-color 0.15s;
}

.settings-field input:focus {
  border-color: var(--color-accent);
}

.model-select-wrapper select,
.model-select-wrapper input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-primary);
  background: var(--color-surface-base);
  outline: none;
  transition: border-color 0.15s;
}

.model-select-wrapper select:focus,
.model-select-wrapper input:focus {
  border-color: var(--color-accent);
}

.model-select {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%238e99a8' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 36px;
}

.settings-field-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  font-size: 13px;
  color: var(--color-text-primary);
}

.field-hint {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.toggle-btn {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: var(--color-border-strong);
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
}

.toggle-btn.active {
  background: var(--color-accent);
}

.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  transition: left 0.2s;
}

.toggle-btn.active .toggle-knob {
  left: 22px;
}

.font-slider {
  width: 100%;
  height: 4px;
  appearance: none;
  background: var(--color-border-subtle);
  border-radius: 2px;
  outline: none;
  margin-top: 4px;
}

.font-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-accent);
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0,0,0,0.15);
}

/* Storage */
.storage-usage {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  font-size: 13px;
  color: var(--color-text-primary);
}

.storage-value {
  font-weight: 500;
  color: var(--color-accent);
}

.storage-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.storage-btn {
  flex: 1;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  color: var(--color-text-primary);
  background: var(--color-surface-base);
  cursor: pointer;
  transition: background 0.15s;
}

.storage-btn:hover {
  background: var(--color-surface-muted);
}

.storage-btn-danger {
  color: #d32f2f;
  border-color: rgba(211, 47, 47, 0.2);
}

.storage-btn-danger:hover {
  background: rgba(211, 47, 47, 0.06);
}

/* Theme switcher */
.theme-switcher {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

.theme-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  color: var(--color-text-secondary);
  background: var(--color-surface-base);
  cursor: pointer;
  transition: all 0.15s;
}

.theme-option:hover {
  background: var(--color-surface-muted);
}

.theme-option.active {
  border-color: var(--color-accent);
  color: var(--color-accent);
  background: var(--color-accent-soft);
}

/* About section */
.about-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

.about-logo {
  display: flex;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.about-logo :deep(svg) {
  width: 100%;
  height: 100%;
}

.about-logo:hover {
  transform: scale(1.08);
}

.about-version {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.about-body {
  padding-top: 14px;
  border-top: 1px solid var(--color-border-subtle);
}

.about-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin-bottom: 12px;
}

.about-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.about-tag {
  padding: 3px 10px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 99px;
  background: var(--color-surface-muted);
  color: var(--color-text-secondary);
}

.about-links {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.about-link-divider {
  opacity: 0.4;
}

/* Easter egg overlay */
.easter-overlay {
  position: fixed;
  inset: 0;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(6px);
  cursor: pointer;
  animation: easter-fade-in 0.4s ease;
}

@keyframes easter-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.easter-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.easter-lottie {
  width: 220px;
  height: 220px;
}

.easter-text {
  font-size: 36px;
  font-weight: 900;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: #fff;
  text-shadow:
    0 1px 0 #ccc,
    0 2px 0 #c9c9c9,
    0 3px 0 #bbb,
    0 4px 0 #b9b9b9,
    0 5px 0 #aaa,
    0 6px 1px rgba(0,0,0,.1),
    0 0 5px rgba(24,94,234,.15),
    0 1px 3px rgba(0,0,0,.3),
    0 3px 5px rgba(0,0,0,.2),
    0 5px 10px rgba(0,0,0,.25),
    0 10px 10px rgba(0,0,0,.2),
    0 20px 20px rgba(0,0,0,.15);
  animation: easter-text-glow 2s ease-in-out infinite alternate;
}

@keyframes easter-text-glow {
  from {
    text-shadow:
      0 1px 0 #ccc,
      0 2px 0 #c9c9c9,
      0 3px 0 #bbb,
      0 4px 0 #b9b9b9,
      0 5px 0 #aaa,
      0 6px 1px rgba(0,0,0,.1),
      0 0 5px rgba(24,94,234,.15),
      0 1px 3px rgba(0,0,0,.3),
      0 3px 5px rgba(0,0,0,.2),
      0 5px 10px rgba(0,0,0,.25),
      0 10px 10px rgba(0,0,0,.2),
      0 20px 20px rgba(0,0,0,.15);
  }
  to {
    text-shadow:
      0 1px 0 #ccc,
      0 2px 0 #c9c9c9,
      0 3px 0 #bbb,
      0 4px 0 #b9b9b9,
      0 5px 0 #aaa,
      0 6px 1px rgba(0,0,0,.1),
      0 0 20px rgba(24,94,234,.6),
      0 0 40px rgba(24,94,234,.4),
      0 0 60px rgba(24,94,234,.2),
      0 1px 3px rgba(0,0,0,.3),
      0 5px 10px rgba(0,0,0,.25),
      0 20px 20px rgba(0,0,0,.15);
  }
}
</style>
