<template>
  <div class="history-item" :class="{ 'history-item--selecting': selectable }">
    <label v-if="selectable" class="history-select" @click.stop>
      <input
        type="checkbox"
        :checked="selected"
        @change="emit('toggle-select', conversation.session_id)"
      >
    </label>

    <button
      class="history-main"
      type="button"
      @click="handleMainClick"
    >
      <template v-if="editing">
        <input
          ref="inputRef"
          v-model="editingTitle"
          class="history-rename-input"
          type="text"
          @click.stop
          @keydown.enter.prevent="submitRename"
          @keydown.esc.prevent="cancelRename"
          @blur="submitRename"
        >
      </template>
      <template v-else>
        <div class="history-preview" :title="conversation.preview || '对话'">
          {{ conversation.preview || '对话' }}
        </div>
      </template>
      <div class="history-meta">
        <span>{{ conversation.msg_count }} 条消息</span>
        <span>{{ formatTime(conversation.last_active) }}</span>
      </div>
    </button>

    <div v-if="!selectable" class="history-actions">
      <button class="more-button" type="button" aria-label="更多操作" @click.stop="toggleMenu">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <circle cx="3" cy="8" r="1.3" />
          <circle cx="8" cy="8" r="1.3" />
          <circle cx="13" cy="8" r="1.3" />
        </svg>
      </button>
      <ContextMenu
        v-if="showMenu"
        @pin="handlePin"
        @share="handleShare"
        @rename="startRename"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import ContextMenu from './ContextMenu.vue'

interface ConversationSummary {
  session_id: string
  msg_count: number
  last_active: string
  preview: string
}

const props = withDefaults(defineProps<{
  conversation: ConversationSummary
  selectable?: boolean
  selected?: boolean
}>(), {
  selectable: false,
  selected: false,
})

const emit = defineEmits<{
  (e: 'load', sessionId: string): void
  (e: 'pin', conv: ConversationSummary): void
  (e: 'share', conv: ConversationSummary): void
  (e: 'rename', payload: { sessionId: string; title: string }): void
  (e: 'toggle-select', sessionId: string): void
}>()

const showMenu = ref(false)
const editing = ref(false)
const editingTitle = ref('')
const inputRef = ref<HTMLInputElement>()

function toggleMenu() {
  showMenu.value = !showMenu.value
}

function handlePin() {
  showMenu.value = false
  emit('pin', props.conversation)
}

function handleShare() {
  showMenu.value = false
  emit('share', props.conversation)
}

function handleMainClick() {
  if (props.selectable) {
    emit('toggle-select', props.conversation.session_id)
    return
  }
  emit('load', props.conversation.session_id)
}

async function startRename() {
  showMenu.value = false
  editing.value = true
  editingTitle.value = props.conversation.preview || '对话'
  await nextTick()
  inputRef.value?.focus()
  inputRef.value?.select()
}

function submitRename() {
  const title = editingTitle.value.trim()
  editing.value = false
  if (!title || title === props.conversation.preview) return
  emit('rename', { sessionId: props.conversation.session_id, title })
}

function cancelRename() {
  editing.value = false
}

function handleDocumentClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.closest('.history-actions')) {
    showMenu.value = false
  }
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour} 小时前`
    const diffDay = Math.floor(diffHour / 24)
    if (diffDay < 7) return `${diffDay} 天前`
    return `${d.getMonth() + 1}/${d.getDate()}`
  } catch {
    return ''
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped>
.history-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border-radius: 10px;
  transition: background 0.15s ease;
}

.history-item:hover,
.history-item--selecting {
  background: rgba(0, 0, 0, 0.04);
}

.history-item:hover .more-button {
  opacity: 1;
}

.history-select {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-height: 40px;
}

.history-main {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  padding: 0;
}

.history-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--color-text-primary);
  line-height: 1.4;
}

.history-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 3px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.history-actions {
  position: relative;
  flex-shrink: 0;
}

.more-button {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  opacity: 0;
  transition: all 0.15s ease;
}

.more-button:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--color-text-primary);
}

.history-rename-input {
  width: 100%;
  border: 0.5px solid rgba(0, 0, 0, 0.12);
  border-radius: 6px;
  background: white;
  padding: 4px 6px;
  font-size: 13px;
  color: var(--color-text-primary);
  outline: none;
}
</style>
