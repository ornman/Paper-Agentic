<template>
  <div class="message-list">
    <template v-for="message in messages" :key="message.id">
      <UserMessage
        v-if="message.role === 'user'"
        :message="message"
      />
      <AIMessage
        v-else
        :message="message"
        :is-streaming="isStreaming && message.id === lastAssistantId"
        @citation-hover="(sourceId, event) => emit('citation-hover', sourceId, event)"
        @citation-leave="emit('citation-leave')"
        @citation-click="(sourceId) => emit('citation-click', sourceId)"
      />
    </template>

    <!-- 打字指示器 -->
    <div v-if="showTyping" class="typing-dots">
      <span></span>
      <span></span>
      <span></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConversationRecord, AssistantMessage } from '../stores/conversation'
import UserMessage from './UserMessage.vue'
import AIMessage from './AIMessage.vue'

const props = defineProps<{
  messages: ConversationRecord[]
  status: string
}>()

const emit = defineEmits<{
  (e: 'citation-hover', sourceId: string, event: MouseEvent): void
  (e: 'citation-leave'): void
  (e: 'citation-click', sourceId: string): void
}>()

const isStreaming = computed(() => props.status === 'streaming' || props.status === 'thinking')
const showTyping = computed(() => props.status === 'requesting')

const lastAssistantId = computed(() => {
  const last = [...props.messages].reverse().find((m): m is AssistantMessage => m.role === 'assistant')
  return last?.id ?? null
})
</script>

<style scoped>
.message-list {
  display: flex;
  flex-direction: column;
}

.typing-dots {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  background: var(--color-text-muted);
  border-radius: 50%;
  animation: typing-dot 1.4s infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-dot {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-4px); }
}
</style>
