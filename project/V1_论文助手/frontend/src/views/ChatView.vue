<template>
  <div class="chat-view">
    <div class="messages-container" ref="messagesContainer">
      <MessageList :messages="store.messages" :status="store.status" />
      <EmptyState v-if="store.messages.length === 0" />
    </div>

    <div class="input-container">
      <div class="input-wrapper">
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="input-field"
          placeholder="输入您的问题..."
          rows="3"
          @keydown.exact.enter.prevent="handleSend"
          :disabled="store.status === 'requesting' || store.status === 'streaming'"
        />
        <button
          class="send-btn"
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
      <div v-if="store.errorMessage" class="error-message">
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
.chat-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.input-container {
  flex-shrink: 0;
  padding: 12px 16px;
  background: white;
  border-top: 1px solid #e5e5e5;
}

.input-wrapper {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-field {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
}

.input-field:focus {
  border-color: #6aae6a;
}

.input-field:disabled {
  background: #f5f5f5;
  color: #b3b3b3;
}

.send-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #6aae6a;
  border: none;
  border-radius: 6px;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: #5a9e5a;
}

.send-btn:active:not(:disabled) {
  background: #4a8e4a;
}

.send-btn:disabled {
  background: #d9d9d9;
  cursor: not-allowed;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-message {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  font-size: 13px;
  color: #ff4d4f;
}
</style>
