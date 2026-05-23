<template>
  <div class="assistant-message">
    <div class="assistant-content">
      <div class="assistant-bubble">
        <div v-if="!message.content" class="empty-content">
          <span class="cursor"></span>
        </div>
        <div v-else class="content-text" v-html="formattedContent" @click="handleContentClick"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConversationAssistantMessage } from '../stores/conversation'
import type { SourceCard } from '../types/source'

const props = defineProps<{
  message: ConversationAssistantMessage
  isStreaming?: boolean
}>()

const emit = defineEmits<{
  (event: 'open-source', source: SourceCard): void
}>()

function activateSourceByIndex(indexText: string) {
  const index = Number(indexText) - 1
  const source = props.message.sources?.[index]
  if (!source) return
  emit('open-source', source)
}

function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function buildSourceLabel(indexText: string) {
  const index = Number(indexText) - 1
  const source = props.message.sources?.[index]
  if (!source) {
    return `[${indexText}]`
  }

  const parts = [source.title]
  if (source.page) {
    parts.push(`第 ${source.page} 页`)
  }
  return parts.join(' · ')
}

const formattedContent = computed(() => {
  const text = escapeHtml(props.message.content)
  return text
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\[(\d+)\]/g, (_match, num) => {
      const label = buildSourceLabel(num)
      return `<button class="source-ref" type="button" data-source-index="${num}" title="${label}">${label}</button>`
    })
    .replace(/\n/g, '<br>')
})

function handleContentClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  const sourceIndex = target.closest('[data-source-index]')?.getAttribute('data-source-index')
  if (!sourceIndex) return
  activateSourceByIndex(sourceIndex)
}
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
}

.assistant-bubble {
  padding: var(--space-3) var(--space-4);
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: var(--radius-lg);
  border-bottom-left-radius: 6px;
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
  min-width: 22px;
  height: 20px;
  padding: 0 5px;
  margin: 0 2px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text-secondary);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  vertical-align: baseline;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.content-text :deep(.source-ref:hover) {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.08);
  color: var(--color-text-primary);
}
</style>
