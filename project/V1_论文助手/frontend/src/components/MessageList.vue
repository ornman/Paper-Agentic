<template>
  <div class="message-list">
    <div v-for="message in messages" :key="message.id" class="message-item">
      <UserMessage v-if="message.role === 'user'" :message="message" />
      <AssistantMessage
        v-else
        :message="message"
        :is-streaming="isStreaming && message === lastAssistantMessage"
      />
    </div>
    <div v-if="status === 'requesting'" class="typing-indicator">
      <span></span>
      <span></span>
      <span></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConversationRecord, ConversationAssistantMessage } from '../stores/conversation'
import UserMessage from './UserMessage.vue'
import AssistantMessage from './AssistantMessage.vue'

const props = defineProps<{
  messages: ConversationRecord[]
  status: 'idle' | 'requesting' | 'streaming' | 'done' | 'error'
}>()

const isStreaming = computed(() => props.status === 'streaming')

const lastAssistantMessage = computed(() => {
  const assistantMessages = props.messages.filter(
    (m): m is ConversationAssistantMessage => m.role === 'assistant'
  )
  return assistantMessages[assistantMessages.length - 1]
})
</script>

<style scoped>
.message-list {
  display: flex;
  flex-direction: column;
  gap: var(--claude-spacing-lg);
}

.message-item {
  display: flex;
  flex-direction: column;
}

.typing-indicator {
  display: flex;
  gap: var(--claude-spacing-xs);
  padding: 12px 16px;
  background: var(--claude-bg-muted);
  border-radius: var(--claude-radius-lg);
  border-bottom-left-radius: var(--claude-radius-sm);
  width: fit-content;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--claude-text-muted);
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-4px);
  }
}
</style>
