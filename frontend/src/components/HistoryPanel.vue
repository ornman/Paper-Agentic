<template>
  <div class="history-panel">
    <!-- Search (always visible) -->
    <div class="history-search">
      <svg class="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        placeholder="搜索对话历史..."
        aria-label="搜索对话历史"
      />
    </div>

    <div v-if="loading" class="history-empty">正在加载...</div>

    <div v-else-if="sessions.length === 0" class="empty-state">
      <svg class="empty-icon" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <p class="empty-text">暂无对话历史，开始你的第一次提问</p>
    </div>

    <div v-else class="history-list">
      <div
        v-for="session in filteredSessions"
        :key="session.session_id"
        class="history-item"
        :class="{ 'history-item--active': session.session_id === activeSessionId }"
        tabindex="0"
        role="button"
        @click="emit('select', session.session_id)"
        @keydown.enter="emit('select', session.session_id)"
      >
        <div class="history-item-info">
          <div class="history-item-title">{{ session.title }}</div>
          <div class="history-item-date">{{ formatDate(session.updated_at) }}</div>
        </div>

        <button
          class="history-item-delete"
          type="button"
          aria-label="删除此会话"
          @click.stop="handleDelete(session)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ConversationSession } from '../services/conversation-api'

const props = defineProps<{
  sessions: ConversationSession[]
  loading: boolean
  activeSessionId: string
}>()

const searchQuery = ref('')

const filteredSessions = computed(() => {
  if (!searchQuery.value.trim()) return props.sessions
  const q = searchQuery.value.toLowerCase()
  return props.sessions.filter(
    (session) => session.title.toLowerCase().includes(q),
  )
})

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'delete', id: string): void
}>()

function handleDelete(session: ConversationSession) {
  if (confirm(`确认删除会话「${session.title}」？此操作不可撤销。`)) {
    emit('delete', session.session_id)
  }
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.history-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* ─── Search ─── */
.history-search {
  position: relative;
  padding: var(--space-2) var(--space-3);
}

.search-icon {
  position: absolute;
  left: calc(var(--space-3) + 10px);
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: var(--space-2) var(--space-3) var(--space-2) 36px;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-full);
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  outline: none;
  transition: border-color var(--duration-fast) ease;
}

.search-input::placeholder {
  color: var(--color-text-muted);
}

.search-input:focus {
  border-color: var(--color-accent);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-6) var(--space-4);
  color: var(--color-text-muted);
}

.empty-icon {
  margin-bottom: var(--space-3);
  opacity: 0.5;
}

.empty-text {
  font-size: 13px;
  margin: 0;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--duration-fast) ease;
}

.history-item:hover {
  background: var(--color-surface-muted);
}

.history-item--active {
  background: var(--color-surface-muted);
}

.history-item--active .history-item-title {
  font-weight: 500;
}

.history-item-info {
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-date {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.history-item-delete {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: var(--color-text-muted);
  opacity: 0;
  transition: opacity var(--duration-fast) ease, color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.history-item:hover .history-item-delete {
  opacity: 1;
}

.history-item-delete:hover {
  color: var(--color-error);
  background: var(--color-surface-muted);
}
</style>
