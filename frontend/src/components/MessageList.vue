<template>
  <section class="message-list" aria-label="消息列表">
    <div v-for="message in messages" :key="message.id" class="message-row">
      <div class="message-shell" :data-message-role="message.role">
        <UserMessage v-if="message.role === 'user'" :message="message" />
        <AssistantMessage
          v-else
          :message="message"
          :is-streaming="isStreaming && message === lastAssistantMessage"
          @open-source="emit('open-source', $event)"
        />
      </div>
    </div>
    <div v-if="status === 'requesting'" class="typing-indicator">
      <span></span>
      <span></span>
      <span></span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConversationRecord, ConversationAssistantMessage } from '../stores/conversation'
import type { SourceCard } from '../types/source'
import UserMessage from './UserMessage.vue'
import AssistantMessage from './AssistantMessage.vue'

const emit = defineEmits<{
  (event: 'open-source', source: SourceCard): void
}>()

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
  display: grid;
  gap: var(--space-4);
}

.message-row {
  display: block;
}

.message-shell {
  width: 100%;
}

.typing-indicator {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-4);
  background: var(--color-assistant-bg);
  border-radius: var(--radius-md);
  border-bottom-left-radius: var(--radius-sm);
  width: fit-content;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: var(--color-text-muted);
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
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-4px); }
}
</style>
