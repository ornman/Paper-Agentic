<script setup lang="ts">
import { ref, computed } from 'vue'

const serverUrl = ref('http://127.0.0.1:8000')
const llmProvider = ref('deepseek')
const model = ref('deepseek-chat')

const providers = [
  { id: 'deepseek', name: 'DeepSeek', models: ['deepseek-chat', 'deepseek-reasoner'] },
  { id: 'zhipu', name: '智谱 GLM', models: ['glm-4', 'glm-4-flash'] },
  { id: 'openai', name: 'OpenAI', models: ['gpt-4', 'gpt-3.5-turbo'] }
]

const currentProvider = computed(() => providers.find(p => p.id === llmProvider.value))
</script>

<template>
  <div class="settings-page">
    <h2>设置</h2>

    <!-- 服务配置 -->
    <div class="settings-section">
      <h3>服务配置</h3>
      <div class="setting-item">
        <label>后端服务地址</label>
        <input v-model="serverUrl" type="text" placeholder="http://127.0.0.1:8000" />
      </div>
      <div class="setting-item">
        <label>连接状态</label>
        <span class="status-badge offline">未连接（演示模式）</span>
      </div>
    </div>

    <!-- LLM 配置 -->
    <div class="settings-section">
      <h3>语言模型配置</h3>
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
        <span class="hint">在真实版本中配置</span>
      </div>
    </div>

    <!-- 关于 -->
    <div class="settings-section">
      <h3>关于</h3>
      <div class="about-info">
        <p><strong>WPS 论文写作辅助工具</strong></p>
        <p>版本: 0.1.0 (UI 原型)</p>
        <p>基于私有文献知识库的论文写作辅助工具</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
  max-width: 600px;
}

.settings-page h2 {
  margin-bottom: 24px;
}

.settings-section {
  background: var(--bg-sidebar);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.settings-section h3 {
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item label {
  width: 120px;
  flex-shrink: 0;
  font-size: 14px;
}

.setting-item input,
.setting-item select {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
}

.setting-item input:focus,
.setting-item select:focus {
  outline: none;
  border-color: var(--primary);
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.status-badge.offline {
  background: rgba(239, 68, 68, 0.2);
  color: var(--error);
}

.status-badge.online {
  background: rgba(16, 163, 127, 0.2);
  color: var(--success);
}

.hint {
  font-size: 12px;
  color: var(--text-secondary);
}

.about-info {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.about-info strong {
  color: var(--text-primary);
}
</style>
