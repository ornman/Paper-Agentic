<template>
  <div class="user-message" @mouseenter="actionsVisible = true" @mouseleave="actionsVisible = false">
    <!-- 编辑态 -->
    <div v-if="isEditing" class="user-edit-wrapper">
      <textarea
        ref="editTextarea"
        v-model="editText"
        class="user-edit-textarea"
        @keydown="handleEditKeydown"
      />
      <div class="edit-actions">
        <button class="edit-cancel-btn" type="button" @click="isEditing = false">取消</button>
        <button class="edit-submit-btn" type="button" :disabled="!editText.trim()" @click="submitEdit">发送</button>
      </div>
    </div>
    <!-- 正常态 -->
    <div v-else class="user-bubble">{{ message.content }}</div>
    <!-- 操作按钮（非编辑态显示） -->
    <div v-if="!isEditing" class="user-actions" :class="{ visible: actionsVisible }">
      <button class="action-item" type="button" @click="handleCopy">
        <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="4.5" y="4.5" width="8" height="8" rx="1.5"/><path d="M9.5 4.5V3a1.5 1.5 0 0 0-1.5-1.5H3A1.5 1.5 0 0 0 1.5 3v5A1.5 1.5 0 0 0 3 9.5h1.5"/></svg>
        <span>{{ copyLabel }}</span>
      </button>
      <button class="action-item" type="button" @click="startEditing">
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
import { ref, nextTick } from 'vue'
import type { UserMessage as UserMessageType } from '../types/message'

const props = defineProps<{
  message: UserMessageType
}>()

const emit = defineEmits<{
  (e: 'resubmit', messageId: string, newText: string): void
  (e: 'delete', messageId: string): void
}>()

const actionsVisible = ref(false)
const copyLabel = ref('复制')
const isEditing = ref(false)
const editText = ref('')
const editTextarea = ref<HTMLTextAreaElement>()

function startEditing() {
  isEditing.value = true
  editText.value = props.message.content
  nextTick(() => {
    const ta = editTextarea.value
    if (ta) {
      ta.focus()
      ta.setSelectionRange(ta.value.length, ta.value.length)
    }
  })
}

function handleEditKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    isEditing.value = false
  }
}

function submitEdit() {
  const trimmed = editText.value.trim()
  if (!trimmed) return
  isEditing.value = false
  emit('resubmit', props.message.id, trimmed)
}

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

.user-edit-wrapper {
  max-width: 80%;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.user-edit-textarea {
  width: 100%;
  padding: 10px 16px;
  background: var(--color-accent-soft, #e6f0ff);
  color: var(--color-text-primary, #1a1a1a);
  border: 2px solid var(--color-accent);
  border-radius: 18px 18px 6px 18px;
  font-size: var(--font-size-base);
  font-family: inherit;
  line-height: 1.65;
  word-break: break-word;
  white-space: pre-wrap;
  resize: none;
  outline: none;
  min-height: 44px;
  box-sizing: border-box;
}

.edit-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-right: 4px;
}

.edit-cancel-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-border-subtle, #e2e2e2);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.edit-cancel-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.edit-submit-btn {
  padding: 4px 12px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.15s;
}

.edit-submit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.edit-submit-btn:not(:disabled):hover {
  opacity: 0.85;
}

.user-actions {
  display: flex;
  align-items: center;
  gap: 4px;
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
