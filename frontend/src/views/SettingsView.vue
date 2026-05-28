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
        <h2 class="settings-section-title">模型配置</h2>
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
          <span>思考模式</span>
          <button class="toggle-btn" :class="{ active: settingsStore.thinkingEnabled }" @click="settingsStore.toggleThinking()">
            <span class="toggle-knob"></span>
          </button>
        </div>
      </section>

      <!-- 2. 对话行为 -->
      <section class="settings-card">
        <h2 class="settings-section-title">对话行为</h2>
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
            <span>RAG 检索</span>
            <div class="field-hint">基于文献库检索增强回答</div>
          </div>
          <button class="toggle-btn" :class="{ active: settingsStore.ragEnabled }" @click="settingsStore.ragEnabled = !settingsStore.ragEnabled">
            <span class="toggle-knob"></span>
          </button>
        </div>
      </section>

      <!-- 3. 主题与界面 -->
      <section class="settings-card">
        <h2 class="settings-section-title">主题与界面</h2>
        <div class="settings-field-row">
          <span>深色模式</span>
          <button class="toggle-btn" :class="{ active: theme.resolvedTheme.value === 'dark' }" @click="theme.toggle()">
            <span class="toggle-knob"></span>
          </button>
        </div>
        <div class="settings-field">
          <label>字体大小（{{ settingsStore.fontSize }}px）</label>
          <input type="range" :min="12" :max="20" :step="1" :value="settingsStore.fontSize" @input="settingsStore.fontSize = Number(($event.target as HTMLInputElement).value)" class="font-slider">
        </div>
      </section>

      <!-- 4. 存储管理 -->
      <section class="settings-card">
        <h2 class="settings-section-title">存储管理</h2>
        <div class="storage-usage">
          <span>本地存储用量</span>
          <span class="storage-value">{{ storageUsage }}</span>
        </div>
        <div class="storage-actions">
          <button class="storage-btn" @click="handleExport">导出数据</button>
          <button class="storage-btn storage-btn-danger" @click="handleClearCache">清理缓存</button>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useTheme } from '../composables/use-theme'

const settingsStore = useSettingsStore()
const theme = useTheme()

const storageUsage = ref('')

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
  min-height: 100vh;
  background: var(--color-surface-base);
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
  margin-bottom: 14px;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
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
</style>
