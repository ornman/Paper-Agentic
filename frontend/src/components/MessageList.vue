<template>
  <div class="message-list" role="log" aria-live="polite">
    <template v-for="message in messages" :key="message.id">
      <UserMessage
        v-if="message.role === 'user'"
        :message="message"
        @resubmit="onResubmit"
        @delete="onDelete"
      />
      <AIMessage
        v-else
        :message="message"
        :is-streaming="isStreaming && message.id === lastAssistantId"
        :phase-message="isStreaming && message.id === lastAssistantId ? phaseMessage : ''"
        @citation-hover="onCitationHover"
        @citation-leave="emit('citation-leave')"
        @citation-click="onCitationClick"
        @regenerate="onRegenerate"
        @stop="emit('stop')"
        @delete="onDelete"
        @follow-up="onFollowUp"
      />
    </template>

    <!-- 错误状态 -->
    <div v-if="status === 'error'" class="error-banner">
      <span class="error-icon">⚠</span>
      <span class="error-text">{{ errorMessage || '请求失败，请重试' }}</span>
      <button class="error-retry" type="button" @click="emit('retry')">重试</button>
    </div>

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
  errorMessage?: string
  phaseMessage?: string
}>()

const emit = defineEmits<{
  (e: 'citation-hover', sourceId: string, event: MouseEvent): void
  (e: 'citation-leave'): void
  (e: 'citation-click', sourceId: string): void
  (e: 'retry'): void
  (e: 'regenerate', messageId: string): void
  (e: 'stop'): void
  (e: 'delete-message', messageId: string): void
  (e: 'resubmit-message', messageId: string, text: string): void
  (e: 'follow-up', text: string): void
}>()

const isStreaming = computed(() => props.status === 'streaming' || props.status === 'thinking')
const showTyping = computed(() => props.status === 'requesting')

const lastAssistantId = computed(() => {
  const last = [...props.messages].reverse().find((m): m is AssistantMessage => m.role === 'assistant')
  return last?.id ?? null
})

function onResubmit(id: string, text: string) { emit('resubmit-message', id, text) }
function onDelete(id: string) { emit('delete-message', id) }
function onCitationHover(sourceId: string, event: MouseEvent) { emit('citation-hover', sourceId, event) }
function onCitationClick(sourceId: string) { emit('citation-click', sourceId) }
function onRegenerate(id: string) { emit('regenerate', id) }
function onFollowUp(text: string) { emit('follow-up', text) }
</script>

<style scoped>
.message-list {
  display: flex;
  flex-direction: column;
}

.message-list > * {
  animation: message-appear 250ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes message-appear {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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

.error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  margin-top: var(--space-3);
  background: color-mix(in srgb, var(--color-error, #c53030) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-error, #c53030) 25%, transparent);
  border-radius: var(--radius-md);
  color: var(--color-error, #c53030);
  font-size: var(--font-size-base);
}

.error-icon {
  flex-shrink: 0;
  font-size: 16px;
}

.error-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.error-retry {
  flex-shrink: 0;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--color-error, #c53030);
  background: transparent;
  border: 1px solid color-mix(in srgb, var(--color-error, #c53030) 40%, transparent);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--duration-fast) ease;
}

.error-retry:hover {
  background: color-mix(in srgb, var(--color-error, #c53030) 10%, transparent);
}
</style>
