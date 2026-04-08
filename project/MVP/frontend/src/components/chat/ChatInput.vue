<script setup lang="ts">
import { ref } from 'vue'
import { useMockStore } from '../../stores/mockStore'

const store = useMockStore()
const inputText = ref('')
const mode = ref<'qa' | 'continue'>('qa')

function handleSend() {
  if (!inputText.value.trim() || store.isStreaming) return
  store.simulateStreamResponse(inputText.value)
  inputText.value = ''
}
</script>

<template>
  <div class="chat-input">
    <div class="mode-switch">
      <button
        :class="['mode-btn', { active: mode === 'qa' }]"
        @click="mode = 'qa'"
      >
        <svg class="mode-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        问答
      </button>
      <button
        :class="['mode-btn', { active: mode === 'continue' }]"
        @click="mode = 'continue'"
      >
        <svg class="mode-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 19l7-7 3 3-7 7-3-3z"/>
          <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/>
          <path d="M2 2l7.586 7.586"/>
          <circle cx="11" cy="11" r="2"/>
        </svg>
        续写
      </button>
    </div>
    <div class="input-row">
      <textarea
        v-model="inputText"
        placeholder="输入问题或续写提示..."
        @keydown.enter.exact.prevent="handleSend"
        :disabled="store.isStreaming"
        rows="1"
      ></textarea>
      <button
        @click="handleSend"
        :disabled="!inputText.trim() || store.isStreaming"
        class="send-btn"
      >
        <svg v-if="!store.isStreaming" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22,2 15,22 11,13 2,9"/>
        </svg>
        <svg v-else class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  padding: 16px;
  background: var(--bg-sidebar);
  border-top: 1px solid var(--border);
}

.mode-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.mode-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.mode-icon {
  width: 14px;
  height: 14px;
}

.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.input-row textarea {
  flex: 1;
  padding: 12px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 13px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.2s;
}

.input-row textarea:focus {
  outline: none;
  border-color: var(--primary);
}

.input-row textarea::placeholder {
  color: var(--text-secondary);
}

.send-btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: scale(1.02);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-btn svg {
  width: 20px;
  height: 20px;
}

.send-btn svg.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
