<template>
  <div class="user-message" @mouseenter="actionsVisible = true" @mouseleave="actionsVisible = false">
    <div class="user-bubble">{{ message.content }}</div>
    <div class="user-actions" :class="{ visible: actionsVisible }">
        <button class="action-item" type="button" @click="handleCopy">
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="4.5" y="4.5" width="8" height="8" rx="1.5"/><path d="M9.5 4.5V3a1.5 1.5 0 0 0-1.5-1.5H3A1.5 1.5 0 0 0 1.5 3v5A1.5 1.5 0 0 0 3 9.5h1.5"/></svg>
          <span>{{ copyLabel }}</span>
        </button>
        <button class="action-item" type="button" @click="emit('edit', message.id, message.content)">
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M9.5 1.5l3 3L4.5 12.5H1.5v-3z"/></svg>
          <span>编辑</span>
        </button>
        <button class="action-item action-item--danger" type="button" @click="emit('delete', message.id)">
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M2 3.5h10"/><path d="M5.5 3.5V2.5a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1"/><path d="M3 3.5l.5 8a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1l.5-8"/></svg>
          <span>删除</span>
        </button>
      </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { UserMessage as UserMessageType } from '../stores/conversation'

const props = defineProps<{
  message: UserMessageType
}>()

const emit = defineEmits<{
  (e: 'edit', messageId: string, text: string): void
  (e: 'delete', messageId: string): void
}>()

const actionsVisible = ref(false)
const copyLabel = ref('复制')

async function handleCopy() {
  await navigator.clipboard.writeText(props.message.content)
  copyLabel.value = '已复制'
  setTimeout(() => { copyLabel.value = '复制' }, 2000)
}
</script>

<style scoped>
.user-message {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  margin: 12px 0;
}

.user-bubble {
  max-width: 80%;
  padding: 10px 16px;
  background: var(--color-accent);
  color: #ffffff;
  border-radius: 18px 18px 6px 18px;
  font-size: var(--font-size-base);
  line-height: 1.65;
  word-break: break-word;
  white-space: pre-wrap;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.2);
}

.user-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: 4px;
  padding-right: 4px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.user-actions.visible {
  opacity: 1;
  pointer-events: auto;
}

.action-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 6px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.action-item:hover {
  color: var(--color-accent);
  background: var(--color-accent-soft);
}

.action-item--danger:hover {
  color: var(--color-error, #c53030);
  background: color-mix(in srgb, var(--color-error, #c53030) 10%, transparent);
}
</style>
