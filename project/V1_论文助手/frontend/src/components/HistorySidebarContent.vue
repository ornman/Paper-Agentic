<template>
  <section class="sidebar-panel">
    <header class="sidebar-header">
      <h2 class="sidebar-title">历史对话</h2>
      <div class="sidebar-header-actions">
        <button class="header-action-button" type="button" @click="emit('new-chat')">新对话</button>
        <button
          v-if="!showLibrarySection && conversationList.length > 0"
          class="header-action-button"
          type="button"
          @click="toggleBatchSelection"
        >
          {{ selectingHistory ? '取消选择' : '批量删除' }}
        </button>
        <button class="header-action-button" type="button" @click="toggleLibrarySection">
          {{ showLibrarySection ? '对话' : '文献库' }}
        </button>
      </div>
    </header>

    <div v-if="showLibrarySection" class="sidebar-body sidebar-body--library">
      <header class="library-toolbar">
        <button class="library-upload-button" type="button" @click="triggerFileSelect">上传 PDF</button>
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf"
          class="file-input-hidden"
          @change="handleFileSelect"
        >
      </header>

      <div v-if="libraryStore.importing" class="import-progress">
        <div class="import-header">{{ libraryStore.importFileName }}</div>
        <div class="progress-bar-wrapper">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${libraryStore.importPercent}%` }"></div>
          </div>
          <span class="progress-percent">{{ libraryStore.importPercent }}%</span>
        </div>
        <div class="import-step">{{ libraryStore.importStep }}</div>
      </div>

      <div v-if="libraryStore.importError" class="import-error">
        <span>{{ libraryStore.importError }}</span>
        <button class="dismiss-btn" type="button" @click="libraryStore.clearImportError()">关闭</button>
      </div>

      <div class="search-shell">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="7" cy="7" r="5" stroke="#9c978e" stroke-width="1.5" fill="none"/>
          <line x1="11" y1="11" x2="14" y2="14" stroke="#9c978e" stroke-width="1.5"/>
        </svg>
        <input
          v-model="libraryStore.searchQuery"
          class="search-input"
          type="text"
          placeholder="搜索论文..."
        >
      </div>

      <div v-if="libraryStore.loading" class="sidebar-empty">加载中...</div>
      <div v-else-if="libraryStore.error" class="sidebar-empty">{{ libraryStore.error }}</div>
      <div v-else-if="libraryStore.paperCount === 0 && !libraryStore.importing" class="sidebar-empty">
        还没有导入论文
      </div>
      <div v-else class="paper-list">
        <div class="paper-stats">共 {{ libraryStore.paperCount }} 篇</div>
        <div
          v-for="paper in libraryStore.filteredPapers"
          :key="paper.paper_id"
          class="paper-card"
          :class="{ 'paper-card--selected': libraryStore.isPaperSelected(paper.paper_id) }"
          role="button"
          tabindex="0"
          @click="togglePaperSelection(paper.paper_id)"
          @keydown.enter.prevent="togglePaperSelection(paper.paper_id)"
          @keydown.space.prevent="togglePaperSelection(paper.paper_id)"
        >
          <label class="paper-select" @click.stop>
            <input
              type="checkbox"
              :checked="libraryStore.isPaperSelected(paper.paper_id)"
              @change="togglePaperSelection(paper.paper_id)"
            >
          </label>
          <div class="paper-info">
            <div class="paper-title" :title="paper.title">{{ paper.title }}</div>
            <div class="paper-meta">
              <span v-if="paper.authors">{{ paper.authors }}</span>
              <span :title="`已切分为 ${paper.chunk_count} 个检索片段`" class="chunk-count">{{ paper.chunk_count }} 块</span>
              <span>{{ formatDate(paper.import_time) }}</span>
            </div>
          </div>
          <button class="delete-btn" type="button" title="删除" @click.stop="confirmDelete(paper.paper_id)">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <path d="M5 1h4v1H5zM2 3h10v1H2zM3 4h8v8a1 1 0 01-1 1H4a1 1 0 01-1-1V4z"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <div v-else class="sidebar-body sidebar-body--history" :class="{ 'sidebar-body--selecting': selectingHistory }">
      <div v-if="loadingHistory" class="sidebar-empty">加载中...</div>
      <div v-else-if="displayConversations.length === 0" class="sidebar-empty">暂无对话记录</div>
      <div v-else class="history-list">
        <HistoryItem
          v-for="conversation in displayConversations"
          :key="conversation.session_id"
          :conversation="conversation"
          :selectable="selectingHistory"
          :selected="selectedConversationIds.includes(conversation.session_id)"
          @load="resumeConversation"
          @pin="handlePin"
          @share="handleShare"
          @rename="handleRename"
          @toggle-select="toggleConversationSelection"
        />
      </div>
    </div>

    <footer v-if="selectingHistory && !showLibrarySection" class="selection-footer">
      <div class="selection-summary">已选 {{ selectedConversationIds.length }} 条</div>
      <div class="selection-actions">
        <button class="selection-button" type="button" @click="cancelBatchSelection">取消</button>
        <button
          class="selection-button selection-button--danger"
          type="button"
          :disabled="selectedConversationIds.length === 0 || deletingHistory"
          @click="deleteSelectedConversations"
        >
          {{ deletingHistory ? '删除中...' : '删除所选' }}
        </button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { buildApiUrl } from '../services/api-client'
import { useConversationStore } from '../stores/conversation'
import { useLibraryStore } from '../stores/library'
import HistoryItem from './HistoryItem.vue'

interface ConversationSummary {
  session_id: string
  msg_count: number
  last_active: string
  preview: string
  pinned?: boolean
}

const emit = defineEmits<{
  (event: 'new-chat'): void
}>()

const conversationStore = useConversationStore()
const libraryStore = useLibraryStore()
const conversationList = ref<ConversationSummary[]>([])
const loadingHistory = ref(false)
const deletingHistory = ref(false)
const pinnedSessionIds = ref<string[]>([])
const selectedConversationIds = ref<string[]>([])
const selectingHistory = ref(false)
const showLibrarySection = ref(false)
const fileInputRef = ref<HTMLInputElement>()

const displayConversations = computed(() => {
  return [...conversationList.value].sort((a, b) => {
    const aPinned = pinnedSessionIds.value.includes(a.session_id)
    const bPinned = pinnedSessionIds.value.includes(b.session_id)
    if (aPinned !== bPinned) return aPinned ? -1 : 1
    return new Date(b.last_active).getTime() - new Date(a.last_active).getTime()
  })
})

async function loadConversationList() {
  loadingHistory.value = true
  try {
    const response = await fetch(buildApiUrl('/api/v1/conversations/list?limit=100'))
    if (response.ok) {
      conversationList.value = await response.json()
    }
  } finally {
    loadingHistory.value = false
  }
}

function toggleLibrarySection() {
  showLibrarySection.value = !showLibrarySection.value
  if (showLibrarySection.value) {
    cancelBatchSelection()
    void libraryStore.loadPapers()
  }
}

function toggleBatchSelection() {
  if (selectingHistory.value) {
    cancelBatchSelection()
    return
  }
  selectingHistory.value = true
  selectedConversationIds.value = []
}

function cancelBatchSelection() {
  selectingHistory.value = false
  selectedConversationIds.value = []
  deletingHistory.value = false
}

function toggleConversationSelection(sessionId: string) {
  if (selectedConversationIds.value.includes(sessionId)) {
    selectedConversationIds.value = selectedConversationIds.value.filter((id) => id !== sessionId)
    return
  }
  selectedConversationIds.value = [...selectedConversationIds.value, sessionId]
}

function triggerFileSelect() {
  fileInputRef.value?.click()
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files ? Array.from(input.files) : []
  if (files.length === 0) {
    input.value = ''
    return
  }

  try {
    await libraryStore.importFiles(files)
  } catch {
  }

  input.value = ''
}

async function resumeConversation(sessionId: string) {
  if (selectingHistory.value) {
    toggleConversationSelection(sessionId)
    return
  }

  try {
    const response = await fetch(buildApiUrl(`/api/v1/conversations/${sessionId}`))
    if (!response.ok) return
    const data = await response.json()
    conversationStore.loadHistory(data)
  } catch {
  }
}

function handlePin(conversation: ConversationSummary) {
  if (pinnedSessionIds.value.includes(conversation.session_id)) {
    pinnedSessionIds.value = pinnedSessionIds.value.filter(id => id !== conversation.session_id)
    return
  }
  pinnedSessionIds.value = [...pinnedSessionIds.value, conversation.session_id]
}

async function handleShare(conversation: ConversationSummary) {
  const shareText = conversation.preview || 'AIForScience 对话'
  try {
    const wpsApi = (globalThis as { wps?: { OAAssist?: { ShowSharePanel?: (payload: { title: string; text: string }) => void } } }).wps
    if (wpsApi?.OAAssist?.ShowSharePanel) {
      wpsApi.OAAssist.ShowSharePanel({ title: shareText, text: shareText })
      return
    }
    await navigator.clipboard.writeText(shareText)
  } catch {
  }
}

function handleRename(payload: { sessionId: string; title: string }) {
  conversationList.value = conversationList.value.map(item => {
    if (item.session_id !== payload.sessionId) return item
    return {
      ...item,
      preview: payload.title,
    }
  })
}

async function deleteSelectedConversations() {
  if (selectedConversationIds.value.length === 0) {
    return
  }
  if (!confirm(`确定删除所选 ${selectedConversationIds.value.length} 条对话吗？此操作不可撤销。`)) {
    return
  }

  deletingHistory.value = true
  const deletingIds = [...selectedConversationIds.value]

  try {
    for (const sessionId of deletingIds) {
      const response = await fetch(buildApiUrl(`/api/v1/conversations/${sessionId}`), {
        method: 'DELETE',
      })
      if (!response.ok) {
        throw new Error(`删除失败: ${sessionId}`)
      }
    }

    conversationList.value = conversationList.value.filter(item => !deletingIds.includes(item.session_id))
    pinnedSessionIds.value = pinnedSessionIds.value.filter(id => !deletingIds.includes(id))
    if (deletingIds.includes(conversationStore.sessionId)) {
      conversationStore.reset()
    }
    cancelBatchSelection()
  } catch {
    deletingHistory.value = false
  }
}

async function confirmDelete(paperId: string) {
  if (!confirm('确定删除这篇论文？此操作不可撤销。')) return
  try {
    await libraryStore.removePaper(paperId)
  } catch {
  }
}

function togglePaperSelection(paperId: string) {
  libraryStore.togglePaperSelection(paperId)
}

function formatDate(iso: string) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return `${d.getMonth() + 1}/${d.getDate()}`
  } catch {
    return ''
  }
}

onMounted(() => {
  void loadConversationList()
})

watch(
  () => conversationStore.status,
  (status, previousStatus) => {
    if (status === 'done' && previousStatus !== 'done') {
      void loadConversationList()
    }
  },
)
</script>

<style scoped>
.sidebar-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-surface-base);
}

.sidebar-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
}

.sidebar-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-action-button {
  border: 0.5px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  padding: 5px 10px;
  cursor: pointer;
}

.sidebar-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.sidebar-body--library {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sidebar-body--history {
  padding-bottom: 8px;
}

.sidebar-body--selecting {
  padding-bottom: 12px;
}

.sidebar-empty {
  padding: 24px 8px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.library-toolbar {
  display: flex;
  justify-content: flex-end;
}

.library-upload-button {
  border: 0.5px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  padding: 5px 10px;
  cursor: pointer;
}

.file-input-hidden {
  display: none;
}

.import-progress {
  padding: 10px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
}

.import-header {
  font-size: 12px;
  color: var(--color-text-primary);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--color-border-subtle);
  border-radius: 999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-text-primary);
}

.progress-percent,
.import-step {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.import-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  background: var(--color-error-bg);
  border: 1px solid var(--color-error-border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-error);
}

.dismiss-btn {
  border: 1px solid var(--color-error-border);
  background: transparent;
  color: var(--color-error);
  border-radius: 4px;
  font-size: 11px;
  padding: 2px 8px;
  cursor: pointer;
}

.search-shell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  background: var(--color-surface-card);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 13px;
  outline: none;
}

.paper-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.paper-stats {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.paper-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
}

.paper-card--selected {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.18);
}

.paper-select {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.paper-info {
  flex: 1;
  min-width: 0;
}

.paper-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
  max-height: 2.8em;
  margin-bottom: 2px;
}

.paper-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--color-text-muted);
}

.chunk-count {
  cursor: help;
  border-bottom: 1px dotted var(--color-text-secondary);
}

.delete-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  cursor: pointer;
}

.delete-btn:hover {
  color: var(--color-error);
  border-color: var(--color-error-border);
  background: var(--color-error-bg);
}

.selection-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  background: var(--color-surface-card);
}

.selection-summary {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.selection-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selection-button {
  border: 0.5px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  padding: 5px 10px;
  cursor: pointer;
}

.selection-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.selection-button--danger {
  color: var(--color-error);
  border-color: var(--color-error-border);
}
</style>
