<template>
  <div class="claude-chat-view">
    <div class="claude-messages" ref="messagesContainer">
      <MessageList :messages="store.messages" :status="store.status" />
      <EmptyState v-if="store.messages.length === 0" />
    </div>

    <div class="claude-input-area">
      <!-- RAG 开关 -->
      <div class="claude-controls">
        <label class="toggle-switch" :class="{ disabled: isBusy }">
          <input
            type="checkbox"
            v-model="enableRag"
            :disabled="isBusy"
          />
          <span class="toggle-slider"></span>
          <span class="toggle-label">
            <span class="toggle-label-text">文献检索</span>
            <span class="toggle-label-status">{{ enableRag ? '开启' : '关闭' }}</span>
          </span>
        </label>
      </div>

      <div class="claude-input-wrapper">
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="claude-textarea"
          placeholder="输入您的问题..."
          rows="3"
          @keydown.exact.enter.prevent="handleSend"
          :disabled="store.status === 'requesting' || store.status === 'streaming'"
        />
        <button
          class="claude-send-btn"
          @click="handleSend"
          :disabled="!canSend"
          :title="canSend ? '发送 (Enter)' : '请输入内容'"
        >
          <svg v-if="!isBusy" width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path d="M2 10l8-8 8 8M10 2v16"/>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="currentColor" class="spinning">
            <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" fill="none" stroke-dasharray="32" stroke-dashoffset="32"/>
          </svg>
        </button>
      </div>
      <div class="claude-input-footer">
        <span class="claude-input-hint">{{ inputText.length }} / 5000</span>
      </div>
      <div v-if="store.errorMessage" class="claude-error-message">
        {{ store.errorMessage }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useConversationStore } from '../stores/conversation'
import MessageList from '../components/MessageList.vue'
import EmptyState from '../components/EmptyState.vue'

const store = useConversationStore()
const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement>()
const messagesContainer = ref<HTMLElement>()
const enableRag = ref(true)  // RAG 开关状态，默认开启

const isBusy = computed(() => store.status === 'requesting' || store.status === 'streaming')

const canSend = computed(() => {
  return inputText.value.trim() && !isBusy.value
})

async function handleSend() {
  if (!canSend.value) return

  const query = inputText.value.trim()
  inputText.value = ''

  await store.sendPrompt({
    session_id: store.sessionId,
    prompt: query,
    enable_rag: enableRag.value,  // 传递 RAG 开关状态
  })

  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => store.messages.length, () => {
  scrollToBottom()
}, { flush: 'post' })

watch(() => store.status, (s) => {
  if (s === 'streaming' || s === 'done') {
    scrollToBottom()
  }
})
</script>

<style scoped>
.claude-chat-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  background: var(--color-surface-base);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-subtle);
  overflow: hidden;
  position: relative;
}

.claude-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  padding-bottom: var(--space-6);
  min-height: 0;
}

.claude-input-area {
  flex-shrink: 0;
  padding: var(--space-4);
  border-top: 1px solid var(--color-border-subtle);
  background: var(--color-surface-base);
  position: sticky;
  bottom: 0;
  z-index: 10;
}

.claude-controls {
  display: flex;
  align-items: center;
  padding-bottom: var(--space-2);
}

/* ─── Toggle Switch ─── */
.toggle-switch {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
}

.toggle-switch.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-switch input[type="checkbox"] {
  display: none;
}

.toggle-slider {
  position: relative;
  width: 44px;
  height: 24px;
  background: #d1d5db;
  border-radius: 12px;
  transition: background 0.2s ease;
}

.toggle-switch input[type="checkbox"]:checked + .toggle-slider {
  background: var(--color-accent);
}

.toggle-slider::before {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.toggle-switch input[type="checkbox"]:checked + .toggle-slider::before {
  transform: translateX(20px);
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.toggle-label-text {
  font-size: 13px;
  color: var(--color-text-primary);
  font-weight: 500;
}

.toggle-label-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--color-surface-muted);
  color: var(--color-text-secondary);
  font-weight: 600;
}

.toggle-switch input[type="checkbox"]:checked ~ .toggle-label .toggle-label-status {
  background: var(--color-accent);
  color: white;
}

.claude-input-wrapper {
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
}

.claude-textarea {
  flex: 1;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  font-family: inherit;
  background: var(--color-surface-card);
  color: var(--color-text-primary);
  transition: border-color 0.2s ease;
}

.claude-textarea:focus {
  border-color: var(--color-accent);
  outline: none;
}

.claude-textarea:disabled {
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
}

.claude-input-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-1);
}

.claude-input-hint {
  font-size: 12px;
  color: var(--color-text-muted);
}

.claude-send-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent);
  border: none;
  border-radius: var(--radius-md);
  color: white;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.claude-send-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.claude-send-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.claude-send-btn:disabled {
  background: var(--color-border-subtle);
  cursor: not-allowed;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.claude-error-message {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-error-bg);
  border: 1px solid var(--color-error-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--color-error);
}
</style>
