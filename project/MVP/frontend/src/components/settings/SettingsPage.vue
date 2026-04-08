<script setup lang="ts">
import { ref, computed } from 'vue'
import { useThemeStore, themes } from '../../stores/themeStore'

const themeStore = useThemeStore()

const serverUrl = ref('http://127.0.0.1:8000')
const llmProvider = ref('deepseek')
const model = ref('deepseek-chat')

const providers = [
  { id: 'deepseek', name: 'DeepSeek', models: ['deepseek-chat', 'deepseek-reasoner'] },
  { id: 'zhipu', name: '智谱 GLM', models: ['glm-4', 'glm-4-flash'] },
  { id: 'openai', name: 'OpenAI', models: ['gpt-4', 'gpt-3.5-turbo'] }
]

const currentProvider = computed(() => providers.find(p => p.id === llmProvider.value))

const themeOptions = Object.values(themes)
</script>

<template>
  <div class="settings-page">
    <h2>设置</h2>

    <!-- 外观设置 -->
    <div class="settings-section">
      <h3>
        <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
        外观
      </h3>
      <div class="setting-item theme-selector">
        <label>主题风格</label>
        <div class="theme-options">
          <button
            v-for="theme in themeOptions"
            :key="theme.id"
            :class="['theme-btn', { active: themeStore.currentThemeId === theme.id }]"
            @click="themeStore.setTheme(theme.id)"
          >
            <span class="theme-preview" :style="{ background: theme.colors.primary }"></span>
            <span class="theme-name">{{ theme.name }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 服务配置 -->
    <div class="settings-section">
      <h3>
        <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
          <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
          <line x1="6" y1="6" x2="6.01" y2="6"/>
          <line x1="6" y1="18" x2="6.01" y2="18"/>
        </svg>
        服务配置
      </h3>
      <div class="setting-item">
        <label>后端服务地址</label>
        <input v-model="serverUrl" type="text" placeholder="http://127.0.0.1:8000" />
      </div>
      <div class="setting-item">
        <label>连接状态</label>
        <span class="status-badge offline">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          未连接（演示模式）
        </span>
      </div>
    </div>

    <!-- LLM 配置 -->
    <div class="settings-section">
      <h3>
        <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2"/>
        </svg>
        语言模型配置
      </h3>
      <div class="setting-item">
        <label>供应商</label>
        <select v-model="llmProvider">
          <option v-for="p in providers" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
      </div>
      <div class="setting-item">
        <label>模型</label>
        <select v-model="model">
          <option v-for="m in currentProvider?.models" :key="m" :value="m">
            {{ m }}
          </option>
        </select>
      </div>
      <div class="setting-item">
        <label>API Key</label>
        <input type="password" value="sk-****" disabled />
        <span class="hint">在完整版中配置</span>
      </div>
    </div>

    <!-- 关于 -->
    <div class="settings-section about">
      <h3>
        <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="16" x2="12" y2="12"/>
          <line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>
        关于
      </h3>
      <div class="about-info">
        <p class="app-name">WPS 论文写作辅助工具</p>
        <p class="version">版本 0.1.0 (UI 原型)</p>
        <p class="desc">基于私有文献知识库的论文写作辅助工具</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
  max-width: 100%;
}

.settings-page h2 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 20px;
  color: var(--text-primary);
}

.settings-section {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--border);
  transition: background-color 0.3s, border-color 0.3s;
}

.settings-section h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-icon {
  width: 18px;
  height: 18px;
  color: var(--primary);
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.setting-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.setting-item label {
  width: 100px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.setting-item input,
.setting-item select {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  transition: border-color 0.2s, background-color 0.3s;
}

.setting-item input:focus,
.setting-item select:focus {
  outline: none;
  border-color: var(--primary);
}

.setting-item input:disabled {
  opacity: 0.6;
}

/* Theme Selector */
.theme-selector {
  flex-direction: column;
  align-items: flex-start;
}

.theme-selector label {
  margin-bottom: 10px;
}

.theme-options {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  width: 100%;
}

.theme-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-input);
  border: 2px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.theme-btn:hover {
  border-color: var(--primary);
}

.theme-btn.active {
  border-color: var(--primary);
  background: rgba(0, 0, 0, 0.03);
}

.theme-preview {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  flex-shrink: 0;
}

.theme-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge svg {
  width: 14px;
  height: 14px;
}

.status-badge.offline {
  background: rgba(239, 68, 68, 0.1);
  color: var(--error);
}

.hint {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.about-info {
  text-align: center;
  padding: 8px 0;
}

.about-info .app-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.about-info .version {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.about-info .desc {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
