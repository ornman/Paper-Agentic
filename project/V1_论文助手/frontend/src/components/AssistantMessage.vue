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

  // 简单的 Markdown 格式化
  return text
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
})
</script>

<style scoped>
.assistant-message {
  display: flex;
  justify-content: flex-start;
}

.assistant-content {
  max-width: 85%;
  display: flex;
  flex-direction: column;
  gap: var(--claude-spacing-md);
}

.assistant-bubble {
  padding: var(--claude-spacing-md) var(--claude-spacing-lg);
  background: var(--claude-bg-muted);
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-lg);
  border-bottom-left-radius: var(--claude-radius-sm);
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
  background: var(--claude-primary);
  margin-left: 2px;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.content-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--claude-text-primary);
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
  background: var(--claude-bg-muted);
  border-radius: 3px;
  font-family: 'Consolas', monospace;
  font-size: 13px;
}
</style>
