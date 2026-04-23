<template>
  <div class="assistant-message">
    <div class="assistant-content">
      <div class="assistant-bubble">
        <div v-if="!message.content" class="empty-content">
          <span class="cursor"></span>
        </div>
        <div v-else class="content-text" v-html="formattedContent"></div>
      </div>

      <SourceCardList
        v-if="message.sources && message.sources.length > 0"
        :sources="message.sources"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConversationAssistantMessage } from '../stores/conversation'
import SourceCardList from './SourceCardList.vue'

const props = defineProps<{
  message: ConversationAssistantMessage
  isStreaming?: boolean
}>()

const formattedContent = computed(() => {
  const text = props.message.content
  return text
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\[(\d+)\]/g, (_match, num) => {
      return `<span class="source-ref">[${num}]</span>`
    })
    .replace(/\n/g, '<br>')
})
</script>

<style scoped>
.assistant-message {
  display: flex;
  justify-content: flex-start;
}

.assistant-content {
  max-width: 88%;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.assistant-bubble {
  padding: var(--space-3) var(--space-4);
  background: #f0f4ff;
  border: 1px solid #d0d9ff;
  border-radius: var(--radius-md);
  border-bottom-left-radius: 6px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
}

.empty-content {
  min-height: 24px;
  position: relative;
}

.cursor::after {
  content: '';
  display: inline-block;
  width: 2px;
  height: 16px;
  background: var(--color-text-primary);
  margin-left: 2px;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.content-text {
  font-size: var(--font-size-body);
  line-height: 1.8;
  color: var(--color-text-primary);
  word-break: break-word;
}

.content-text :deep(strong) {
  font-weight: 600;
}

.content-text :deep(em) {
  font-style: italic;
}

.content-text :deep(code) {
  padding: 2px 6px;
  background: var(--color-surface-base);
  border-radius: 4px;
  font-family: 'Consolas', 'Menlo', monospace;
  font-size: 13px;
}

.content-text :deep(.source-ref) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 4px;
  margin: 0 2px;
  background: var(--color-accent);
  color: white;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  vertical-align: baseline;
}
</style>
