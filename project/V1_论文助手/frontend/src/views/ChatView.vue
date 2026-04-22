<template>
  <div class="claude-chat-view">
    <div class="claude-messages" ref="messagesContainer">
      <MessageList :messages="store.messages" :status="store.status" />
      <EmptyState v-if="store.messages.length === 0" />
    </div>

    <div class="claude-input-area">
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
  background: var(--claude-bg-card);
  border-radius: var(--claude-radius-lg);
  border: 1px solid var(--claude-border);
  overflow: hidden;
}

.claude-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--claude-spacing-lg);
}

.claude-input-area {
  flex-shrink: 0;
  padding: var(--claude-spacing-md) var(--claude-spacing-lg);
  border-top: 1px solid var(--claude-border);
  background: var(--claude-bg-card);
}

.claude-input-wrapper {
  display: flex;
  gap: var(--claude-spacing-sm);
  align-items: flex-end;
}

.claude-textarea {
  flex: 1;
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  padding: var(--claude-spacing-md);
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  font-family: inherit;
  background: var(--claude-bg-card);
  color: var(--claude-text-primary);
  transition: border-color 0.2s ease;
}

.claude-textarea:focus {
  border-color: var(--claude-primary);
  outline: none;
}

.claude-textarea:disabled {
  background: var(--claude-bg-muted);
  color: var(--claude-text-muted);
}

.claude-input-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--claude-spacing-xs);
}

.claude-input-hint {
  font-size: 12px;
  color: var(--claude-text-muted);
}

.claude-send-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--claude-primary);
  border: none;
  border-radius: var(--claude-radius-md);
  color: white;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.claude-send-btn:hover:not(:disabled) {
  background: var(--claude-primary-hover);
}

.claude-send-btn:active:not(:disabled) {
  background: var(--claude-primary-hover);
  transform: scale(0.96);
}

.claude-send-btn:disabled {
  background: var(--claude-border);
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
  margin-top: var(--claude-spacing-sm);
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  background: #FFF5F3;
  border: 1px solid #F5C6C0;
  border-radius: var(--claude-radius-sm);
  font-size: 13px;
  color: var(--claude-error);
}
</style>
