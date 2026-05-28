<template>
  <div class="input-bar">
    <div v-if="selectedPaperCount > 0" class="paper-badge" @click="emit('toggle-papers')">
      <span>已选 {{ selectedPaperCount }} 篇文献</span>
      <button class="badge-clear" type="button" @click.stop="emit('clear-papers')">×</button>
    </div>
    <div class="input-row">
      <button class="icon-btn" type="button" title="上传 PDF" @click="triggerUpload">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      </button>
      <textarea
        v-model="text"
        class="composer-input"
        placeholder="输入你的问题..."
        rows="1"
        :disabled="isBusy"
        @keydown.enter.exact.prevent="handleSend"
        @input="autoResize"
      />
      <button class="send-btn" type="button" :disabled="isBusy || !text.trim()" @click="handleSend">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
    <input ref="fileInput" type="file" accept=".pdf" hidden @change="handleFileChange" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  isBusy: boolean
  modelPanelOpen: boolean
  selectedPaperCount: number
}>()

const emit = defineEmits<{
  (e: 'send', text: string): void
  (e: 'upload-pdf', file: File): void
  (e: 'toggle-papers'): void
  (e: 'clear-papers'): void
  (e: 'toggle-model'): void
  (e: 'close-model'): void
}>()

const text = ref('')
const fileInput = ref<HTMLInputElement>()

function handleSend() {
  const trimmed = text.value.trim()
  if (!trimmed) return
  emit('send', trimmed)
  text.value = ''
}

function triggerUpload() {
  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    emit('upload-pdf', file)
    target.value = ''
  }
}

function autoResize(event: Event) {
  const el = event.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}
</script>

<style scoped>
.input-bar {
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface-card);
  border-top: 1px solid var(--color-border-subtle);
}

.paper-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px 10px;
  margin-bottom: var(--space-2);
  font-size: 12px;
  color: var(--color-accent);
  background: var(--color-accent-soft);
  border-radius: var(--radius-full, 9999px);
  cursor: pointer;
}

.badge-clear {
  font-size: 14px;
  line-height: 1;
  color: var(--color-accent);
  cursor: pointer;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
}

.icon-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full, 9999px);
  color: var(--color-text-secondary);
  transition: background 0.15s ease;
}

.icon-btn:hover {
  background: var(--color-surface-muted);
}

.composer-input {
  flex: 1;
  padding: 8px 14px;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-base);
  line-height: 1.5;
  resize: none;
  outline: none;
  background: var(--color-surface-base);
  color: var(--color-text-primary);
  transition: border-color 0.15s ease;
}

.composer-input:focus {
  border-color: var(--color-accent);
}

.composer-input::placeholder {
  color: var(--color-text-muted);
}

.send-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full, 9999px);
  background: var(--color-accent);
  color: #fff;
  transition: opacity 0.15s ease;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn:not(:disabled):hover {
  opacity: 0.85;
}
</style>
