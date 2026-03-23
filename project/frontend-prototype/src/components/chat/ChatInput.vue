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
        问答模式
      </button>
      <button
        :class="['mode-btn', { active: mode === 'continue' }]"
        @click="mode = 'continue'"
      >
        续写模式
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
        {{ store.isStreaming ? '生成中...' : '发送' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  padding: 16px 20px;
  background: var(--bg-sidebar);
  border-top: 1px solid var(--border);
}

.mode-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.mode-btn {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 16px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn:hover {
  border-color: var(--text-secondary);
}

.mode-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-row textarea {
  flex: 1;
  padding: 12px 16px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
}

.input-row textarea:focus {
  outline: none;
  border-color: var(--primary);
}

.send-btn {
  padding: 12px 24px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-hover);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
