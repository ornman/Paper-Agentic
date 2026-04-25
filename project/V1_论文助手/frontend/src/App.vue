<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import type { SourceCard } from './types/source'
import { useConversationStore } from './stores/conversation'
import { useLibraryStore } from './stores/library'
import { useUiStore } from './stores/ui'
import { useWPSPolling } from './composables/wps'
import { useSidebarResize } from './composables/useSidebarResize'
import TopNavBar from './components/TopNavBar.vue'
import HistorySidebarContent from './components/HistorySidebarContent.vue'
import MessageList from './components/MessageList.vue'
import EmptyState from './components/EmptyState.vue'
import SourceCardList from './components/SourceCardList.vue'

const store = useConversationStore()
const libraryStore = useLibraryStore()
const uiStore = useUiStore()

const selectedPaperIds = computed({
  get: () => libraryStore.selectedPaperIds,
  set: (value: string[]) => libraryStore.setSelectedPaperIds(value),
})
const selectedPaperCount = computed(() => libraryStore.selectedPaperCount)
const availablePapers = computed(() => libraryStore.papers)
const isBusy = computed(() => store.status === 'requesting' || store.status === 'streaming')
const canSend = computed(() => inputText.value.trim().length > 0 && !isBusy.value)
const hasMessages = computed(() => store.messages.length > 0)
const sidebarVisible = computed(() => uiStore.sidebarOpen)
const allSources = computed(() => {
  const assistantMessages = store.messages.filter((message) => message.role === 'assistant')
  const lastAssistantMessage = assistantMessages[assistantMessages.length - 1]
  return lastAssistantMessage?.sources ?? []
})
const hasActiveSource = computed(() => activeSource.value !== null)

const { sidebarWidth, isResizing, startResize } = useSidebarResize()
const { startPolling, getSelectedText, isWPSAvailable } = useWPSPolling(true)

const showRetrievalPanel = ref(false)
const retrievalDropdownRef = ref<HTMLElement>()
const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement>()
const messagesContainer = ref<HTMLElement>()
const fileInputRef = ref<HTMLInputElement>()
const dragActive = ref(false)
const activeSource = ref<SourceCard | null>(null)

const MIN_TEXTAREA_HEIGHT = 40
const MAX_TEXTAREA_HEIGHT = 150

function autoResizeTextarea() {
  nextTick(() => {
    const textarea = inputRef.value
    if (!textarea) return
    textarea.style.height = 'auto'
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, MIN_TEXTAREA_HEIGHT), MAX_TEXTAREA_HEIGHT)
    textarea.style.height = `${nextHeight}px`
  })
}

onMounted(() => {
  if (isWPSAvailable.value) {
    startPolling()
  }
  autoResizeTextarea()
  void libraryStore.loadPapers()
  document.addEventListener('click', handleRetrievalPanelClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleRetrievalPanelClickOutside)
})

watch(inputText, () => {
  autoResizeTextarea()
}, { flush: 'post' })

watch(() => store.messages.length, () => {
  scrollToBottom()
}, { flush: 'post' })

watch(() => store.status, (status) => {
  if (status === 'streaming' || status === 'done') {
    scrollToBottom()
  }
})

const lastAssistantContent = computed(() => {
  const lastMessage = store.messages[store.messages.length - 1]
  return lastMessage?.role === 'assistant' ? lastMessage.content : ''
})

watch(lastAssistantContent, () => {
  if (store.status === 'streaming') {
    scrollToBottom()
  }
}, { flush: 'post' })

watch(allSources, (sources) => {
  if (sources.length > 0 && !activeSource.value) {
    activeSource.value = sources[0]
    return
  }

  if (!activeSource.value) {
    return
  }

  const nextActiveSource = sources.find((source) => source.id === activeSource.value?.id)
  activeSource.value = nextActiveSource ?? sources[0] ?? null
})

async function handleSend() {
  if (!canSend.value) return

  let query = inputText.value.trim()
  if (!query && isWPSAvailable.value) {
    query = getSelectedText()
  }
  if (!query) return

  inputText.value = ''

  await store.sendPrompt({
    session_id: store.sessionId,
    prompt: query,
    paper_ids: selectedPaperIds.value,
    enable_rag: selectedPaperIds.value.length > 0,
  })
}

function handleKeydown(event: KeyboardEvent) {
  const nativeEvent = event as KeyboardEvent & { isComposing?: boolean; keyCode?: number }
  if (nativeEvent.isComposing || nativeEvent.keyCode === 229) return
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  void handleSend()
}

function handleNewChat() {
  if (isBusy.value && !confirm('当前对话正在进行中，确定要开始新对话吗？')) {
    return
  }

  store.reset()
  libraryStore.clearSelectedPapers()
  activeSource.value = null
  uiStore.openSidebar()
}

function toggleRetrievalPanel() {
  showRetrievalPanel.value = !showRetrievalPanel.value
  if (showRetrievalPanel.value) {
    void libraryStore.loadPapers()
  }
}

function handleRetrievalPanelClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.closest('.retrieval-dropdown')) {
    showRetrievalPanel.value = false
  }
}

function clearSelectedPapers() {
  libraryStore.clearSelectedPapers()
}

function handleOpenSource(source: SourceCard) {
  activeSource.value = source
}

function closeSourceSidebar() {
  activeSource.value = null
}

function handleSourceCardClick(source: SourceCard) {
  activeSource.value = source
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer?.types.includes('Files')) {
    dragActive.value = true
  }
}

function handleDragLeave(event: DragEvent) {
  if (!(event.currentTarget as HTMLElement)?.contains(event.relatedTarget as Node)) {
    dragActive.value = false
  }
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  dragActive.value = false
  const files = event.dataTransfer?.files ? Array.from(event.dataTransfer.files) : []
  if (files.length > 0) {
    void libraryStore.importFiles(files).catch(() => {})
  }
}

function triggerFileSelect() {
  fileInputRef.value?.click()
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files ? Array.from(input.files) : []
  if (files.length === 0) return

  try {
    await libraryStore.importFiles(files)
  } catch {
  }

  input.value = ''
}

function scrollToBottom() {
  nextTick(() => {
    if (!messagesContainer.value) return
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  })
}
</script>

<template>
  <div
    class="app-shell"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <div class="app-layout">
      <aside
        v-show="sidebarVisible"
        class="history-sidebar"
        :class="{ 'history-sidebar--resizing': isResizing }"
        :style="{ width: `${sidebarWidth}px` }"
      >
        <HistorySidebarContent @new-chat="handleNewChat" />
        <div class="resize-handle" @mousedown="startResize"></div>
      </aside>

      <div class="main-area">
        <div v-if="dragActive" class="drag-overlay">
          <div class="drag-content">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
            <span>松开以导入 PDF</span>
          </div>
        </div>

        <TopNavBar
          :title="store.title || 'AIForScience'"
          @open-history="uiStore.toggleSidebar"
          @new-chat="handleNewChat"
        />

        <main class="content-layout">
          <section class="chat-column">
            <div class="sidebar-content" ref="messagesContainer">
              <div v-if="store.errorMessage" class="conversation-error" role="alert">
                {{ store.errorMessage }}
              </div>
              <MessageList
                v-if="hasMessages"
                :messages="store.messages"
                :status="store.status"
                @open-source="handleOpenSource"
              />
              <EmptyState v-else />
            </div>
          </section>

          <aside v-if="hasActiveSource" class="source-sidebar">
            <header class="source-sidebar-header">
              <div>
                <div class="source-sidebar-kicker">参考资料</div>
                <h2 class="source-sidebar-title">{{ activeSource?.title || '未命名来源' }}</h2>
              </div>
              <button class="source-close-button" type="button" @click="closeSourceSidebar">关闭</button>
            </header>

            <div class="source-sidebar-body">
              <div class="source-focus-card">
                <div class="source-focus-meta">
                  <span v-if="activeSource?.page">第 {{ activeSource.page }} 页</span>
                  <span v-if="activeSource?.section">{{ activeSource.section }}</span>
                </div>
                <p class="source-focus-content">{{ activeSource?.content || '暂无引用原文' }}</p>
              </div>

              <div class="source-sidebar-list-header">本轮来源</div>
              <SourceCardList
                :sources="allSources"
                :active-source-id="activeSource?.id"
                @open-source="handleSourceCardClick"
              />
            </div>
          </aside>
        </main>

        <footer class="bottom-bar">
          <div class="input-container">
            <input
              ref="fileInputRef"
              type="file"
              accept=".pdf"
              multiple
              style="display: none"
              @change="handleFileSelect"
            >

            <textarea
              ref="inputRef"
              v-model="inputText"
              class="composer-input"
              rows="1"
              placeholder="输入您的问题..."
              :disabled="isBusy"
              @keydown="handleKeydown"
            />

            <div class="input-controls-bar">
              <div class="left-controls">
                <button
                  class="attach-button"
                  type="button"
                  title="导入 PDF"
                  @click="triggerFileSelect"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
                  </svg>
                </button>
              </div>

              <div class="middle-spacer"></div>

              <div class="right-controls-group">
                <div class="retrieval-dropdown" ref="retrievalDropdownRef">
                  <button
                    class="retrieval-button"
                    type="button"
                    title="检索增强"
                    @click.stop="toggleRetrievalPanel"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="11" cy="11" r="8"></circle>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                    <span>检索增强</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </button>

                  <div v-if="showRetrievalPanel" class="retrieval-panel" @click.stop>
                    <div class="retrieval-panel-header">
                      <span>选择检索文档</span>
                      <div class="retrieval-panel-summary">
                        <span>{{ selectedPaperCount }}</span>
                        <button
                          v-if="selectedPaperCount > 0"
                          type="button"
                          class="retrieval-clear-button"
                          @click.stop="clearSelectedPapers"
                        >
                          清空
                        </button>
                      </div>
                    </div>
                    <div v-if="availablePapers.length === 0" class="retrieval-empty">
                      暂无可检索文档
                    </div>
                    <div v-else class="retrieval-list">
                      <label
                        v-for="paper in availablePapers"
                        :key="paper.paper_id"
                        class="retrieval-item"
                      >
                        <input
                          v-model="selectedPaperIds"
                          type="checkbox"
                          :value="paper.paper_id"
                        >
                        <span class="retrieval-item-name">{{ paper.title }}</span>
                      </label>
                    </div>
                  </div>
                </div>

                <button
                  class="send-button"
                  type="button"
                  :disabled="!canSend"
                  aria-label="发送"
                  @click="handleSend"
                >
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986l.003-.003.003-.003A60.46 60.46 0 003.478 2.405z"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  width: 100%;
  height: 100%;
  min-height: 100vh;
  display: flex;
  background: var(--color-surface-base);
  color: var(--color-text-primary);
  position: relative;
}

.app-layout {
  flex: 1;
  min-width: 0;
  display: flex;
  overflow: hidden;
}

.history-sidebar {
  position: relative;
  flex-shrink: 0;
  height: 100%;
  min-height: 0;
  background: var(--color-surface-base);
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}

.history-sidebar--resizing {
  user-select: none;
}

.resize-handle {
  position: absolute;
  top: 0;
  right: -8px;
  width: 16px;
  height: 100%;
  cursor: col-resize;
  z-index: 20;
}

.resize-handle::after {
  content: '';
  position: absolute;
  top: 0;
  left: 7px;
  width: 1px;
  height: 100%;
  background: transparent;
}

.resize-handle:hover::after {
  background: rgba(0, 0, 0, 0.12);
}

.main-area {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-surface-base);
}

.drag-overlay {
  position: absolute;
  inset: 0;
  z-index: 50;
  background: rgba(247, 244, 238, 0.92);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drag-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6);
  border: 2px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  color: var(--color-text-primary);
  font-size: 16px;
  font-weight: 500;
}

.content-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.chat-column {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-4) var(--space-3) 16px;
  -webkit-overflow-scrolling: touch;
}

.source-sidebar {
  width: 320px;
  flex-shrink: 0;
  border-left: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.66);
  display: flex;
  flex-direction: column;
}

.source-sidebar-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.source-sidebar-kicker {
  font-size: 11px;
  color: var(--color-text-muted);
  letter-spacing: 0.04em;
}

.source-sidebar-title {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.5;
}

.source-close-button {
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.source-sidebar-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.source-focus-card {
  padding: 14px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
}

.source-focus-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.source-focus-content {
  margin-top: 8px;
  color: var(--color-text-primary);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.source-sidebar-list-header {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.conversation-error {
  margin-bottom: var(--space-3);
  padding: 10px var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-error-border);
  background: var(--color-error-bg);
  color: var(--color-error);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}

.bottom-bar {
  flex-shrink: 0;
  padding: var(--space-3);
  background: transparent;
}

.input-container {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  padding: 10px 14px;
  border: 0.5px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: transparent;
  transition: border-color 0.15s ease;
  min-height: 56px;
  max-height: 200px;
}

.input-container:hover {
  border-color: rgba(0, 0, 0, 0.12);
}

.composer-input {
  flex: 1 1 auto;
  width: 100%;
  min-height: 40px;
  max-height: 150px;
  resize: none;
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  line-height: 1.5;
  font-size: 15px;
  outline: none;
  overflow-y: auto;
  padding: 4px 0;
}

.composer-input::placeholder {
  color: var(--color-text-secondary);
}

.composer-input:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.input-controls-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  min-height: 32px;
}

.left-controls,
.right-controls-group {
  display: flex;
  align-items: center;
}

.middle-spacer {
  flex: 1;
}

.right-controls-group {
  gap: 8px;
}

.attach-button {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all 0.15s ease;
}

.attach-button:hover {
  color: var(--color-text-primary);
  background: rgba(0, 0, 0, 0.06);
}

.send-button {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0.5px solid rgba(0, 0, 0, 0.1);
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.send-button:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.06);
  border-color: rgba(0, 0, 0, 0.15);
  color: var(--color-text-primary);
}

.send-button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.send-button svg {
  width: 16px;
  height: 16px;
}

.retrieval-dropdown {
  position: relative;
}

.retrieval-button {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: 0.5px solid rgba(0, 0, 0, 0.08);
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 400;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.retrieval-button:hover {
  background: rgba(0, 0, 0, 0.03);
  border-color: rgba(0, 0, 0, 0.12);
  color: var(--color-text-primary);
}

.retrieval-panel {
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  width: 300px;
  max-height: 320px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 0.5px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  z-index: 100;
}

.retrieval-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 0.5px solid rgba(0, 0, 0, 0.08);
  font-size: 12px;
  color: var(--color-text-secondary);
}

.retrieval-panel-summary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.retrieval-clear-button {
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.retrieval-clear-button:hover {
  color: var(--color-text-primary);
}

.retrieval-empty {
  padding: 18px 12px;
  font-size: 12px;
  color: var(--color-text-muted);
  text-align: center;
}

.retrieval-list {
  overflow-y: auto;
  padding: 6px;
}

.retrieval-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
}

.retrieval-item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.retrieval-item-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-primary);
  font-size: 12px;
}

@media (max-width: 1200px) {
  .source-sidebar {
    width: 280px;
  }
}
</style>
