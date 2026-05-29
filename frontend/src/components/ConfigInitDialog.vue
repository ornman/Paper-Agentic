<template>
  <Teleport to="body">
    <Transition name="config-overlay">
      <div v-if="visible" class="config-overlay" @click.self="handleBackdropClick">
        <div class="config-dialog">
          <!-- Header -->
          <div class="config-header">
            <img src="../assets/illustrations/research-paper.svg" alt="" class="config-illustration" />
            <h2 class="config-title">初始化配置</h2>
            <p class="config-subtitle">配置 AI 服务以开始使用论文助手</p>
          </div>

          <!-- Form -->
          <div class="config-body">
            <!-- LLM Section -->
            <div class="config-section">
              <h3 class="config-section-title">LLM 主模型</h3>
              <div class="config-field">
                <label>模型厂商</label>
                <select v-model="llmVendor" class="config-select" @change="onVendorChange">
                  <option v-for="v in vendors" :key="v.name" :value="v.name">{{ v.name }}</option>
                </select>
              </div>
              <div class="config-field">
                <label>API Key <span class="required">*</span></label>
                <input v-model="llmApiKey" type="password" placeholder="sk-..." autocomplete="off" />
              </div>
              <p v-if="llmVendor !== '自定义'" class="config-hint">已自动配置 URL 和基础模型</p>
              <template v-else>
                <div class="config-field">
                  <label>Base URL</label>
                  <input v-model="llmBaseUrl" type="text" placeholder="https://api.example.com/v1" />
                </div>
                <div class="config-field">
                  <label>模型名称</label>
                  <input v-model="llmModel" type="text" placeholder="model-name" />
                </div>
              </template>
            </div>

            <!-- Embedding Section -->
            <div class="config-section">
              <h3 class="config-section-title">Embedding（硅基流动）</h3>
              <div class="config-field">
                <label>API Key</label>
                <input v-model="embeddingApiKey" type="password" placeholder="硅基流动 API Key，若 LLM 选硅基流动则填同一个" autocomplete="off" />
              </div>
            </div>

            <!-- MinerU Section -->
            <div class="config-section">
              <h3 class="config-section-title">
                MinerU PDF 解析（可选）
                <span class="optional-tag">可选</span>
              </h3>
              <p class="config-hint">高质量 PDF 解析服务，不填则使用基础文本提取</p>
              <div class="config-field">
                <label>API Key</label>
                <input v-model="mineruApiKey" type="password" placeholder="不填则使用基础解析" autocomplete="off" />
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="config-footer">
            <p v-if="errorMessage" class="config-error">{{ errorMessage }}</p>
            <button
              class="config-submit-btn"
              :disabled="!canSubmit || saving"
              @click="handleSave"
            >
              {{ saving ? '保存中...' : '保存并重启' }}
            </button>
            <span class="config-tutorial-link config-tutorial-disabled">如何获取 API Key？查看教程 &rarr;</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { postJson } from '../services/api-client'

interface Vendor {
  name: string
  baseUrl: string
  model: string
}

const VENDOR_LIST: Vendor[] = [
  { name: 'DeepSeek（默认）', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat' },
  { name: '智谱 GLM', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  { name: '硅基流动', baseUrl: 'https://api.siliconflow.cn/v1', model: 'deepseek-ai/DeepSeek-V3' },
  { name: '月之暗面 Kimi', baseUrl: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { name: '豆包（字节）', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', model: '' },
  { name: '百度千帆', baseUrl: 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop', model: '' },
  { name: '阿里百炼', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  { name: '讯飞星火', baseUrl: 'https://spark-api-open.xf-yun.com/v1', model: 'generalv3.5' },
  { name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o' },
  { name: 'Groq', baseUrl: 'https://api.groq.com/openai/v1', model: 'llama-3.3-70b-versatile' },
  { name: 'Anthropic', baseUrl: 'https://api.anthropic.com/v1', model: 'claude-sonnet-4-20250514' },
  { name: 'Google Gemini', baseUrl: 'https://generativelanguage.googleapis.com/v1beta', model: 'gemini-2.0-flash' },
  { name: '自定义', baseUrl: '', model: '' },
]

const vendors = VENDOR_LIST

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const llmVendor = ref('DeepSeek（默认）')
const llmApiKey = ref('')
const llmBaseUrl = ref('https://api.deepseek.com')
const llmModel = ref('deepseek-chat')
const embeddingApiKey = ref('')
const embeddingBaseUrl = ref('https://api.siliconflow.cn/v1')
const mineruApiKey = ref('')
const mineruBaseUrl = ref('https://mineru.net/api/v4')
const saving = ref(false)
const errorMessage = ref('')

const canSubmit = computed(() => {
  if (!llmApiKey.value.trim()) return false
  if (llmVendor.value === '自定义' && (!llmBaseUrl.value.trim() || !llmModel.value.trim())) return false
  return true
})

function onVendorChange() {
  const v = VENDOR_LIST.find(v => v.name === llmVendor.value)
  if (v) {
    llmBaseUrl.value = v.baseUrl
    llmModel.value = v.model
  }
}

function handleBackdropClick() {
  if (!saving.value) emit('close')
}

async function handleSave() {
  saving.value = true
  errorMessage.value = ''
  try {
    await postJson('/api/v1/config/env', {
      llm_api_key: llmApiKey.value,
      llm_base_url: llmBaseUrl.value,
      llm_model: llmModel.value,
      embedding_api_key: embeddingApiKey.value || undefined,
      embedding_base_url: embeddingBaseUrl.value || undefined,
      mineru_api_key: mineruApiKey.value || undefined,
      mineru_base_url: mineruBaseUrl.value || undefined,
    })
    emit('saved')
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.config-overlay {
  position: fixed;
  inset: 0;
  z-index: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.config-dialog {
  width: 420px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background: var(--color-surface-card);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.config-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28px 24px 16px;
  border-bottom: 1px solid var(--color-border-subtle);
}

.config-illustration {
  width: 140px;
  height: 140px;
  margin-bottom: 12px;
}

.config-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0;
}

.config-subtitle {
  font-size: 13px;
  color: var(--color-text-muted);
  margin: 6px 0 0;
}

.config-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
}

.config-section {
  margin-bottom: 16px;
}

.config-section:last-child {
  margin-bottom: 0;
}

.config-section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 10px;
}

.optional-tag {
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 500;
  border-radius: 4px;
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
}

.config-field {
  margin-bottom: 10px;
}

.config-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.required {
  color: #e53e3e;
}

.config-field input,
.config-select {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-primary);
  background: var(--color-surface-base);
  outline: none;
  transition: border-color 0.15s;
}

.config-field input:focus,
.config-select:focus {
  border-color: var(--color-accent);
}

.config-select {
  appearance: none;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%238e99a8' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 36px;
}

.config-hint {
  font-size: 11px;
  color: var(--color-text-muted);
  margin: 4px 0 0;
}

.config-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--color-border-subtle);
}

.config-submit-btn {
  width: 100%;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  background: var(--color-accent);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: opacity 0.15s;
}

.config-submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.config-submit-btn:not(:disabled):hover {
  opacity: 0.9;
}

.config-tutorial-link {
  font-size: 12px;
  color: var(--color-accent);
  text-decoration: none;
}

.config-tutorial-link:hover {
  text-decoration: underline;
}

.config-tutorial-disabled {
  opacity: 0.5;
  cursor: default;
  pointer-events: none;
}

.config-error {
  width: 100%;
  margin: 0;
  padding: 6px 10px;
  font-size: 12px;
  color: #d32f2f;
  background: rgba(211, 47, 47, 0.06);
  border-radius: 6px;
}

/* Transitions */
.config-overlay-enter-active,
.config-overlay-leave-active {
  transition: opacity 0.25s ease;
}

.config-overlay-enter-active .config-dialog,
.config-overlay-leave-active .config-dialog {
  transition: transform 0.25s ease;
}

.config-overlay-enter-from,
.config-overlay-leave-to {
  opacity: 0;
}

.config-overlay-enter-from .config-dialog,
.config-overlay-leave-to .config-dialog {
  transform: scale(0.95) translateY(10px);
}

@media (max-width: 480px) {
  .config-dialog {
    width: 100%;
    max-height: 100vh;
    border-radius: 0;
  }
}
</style>
