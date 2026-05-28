<template>
  <div class="chat-layout">
    <TopBar @new-chat="handleNewChat" @open-history="handleOpenHistory" />

    <main class="chat-main">
      <!-- 消息区域 -->
      <div class="chat-messages" ref="messagesContainer">
        <div class="chat-messages-inner">
          <MessageList
            :messages="store.messages"
            :status="store.status"
            @citation-hover="handleCitationHover"
            @citation-leave="handleCitationLeave"
            @citation-click="handleCitationClick"
          />
          <EmptyState v-if="store.messages.length === 0 && store.status === 'idle'" />
        </div>
      </div>

      <!-- 底部引用来源面板（最新 assistant 消息的来源） -->
      <SourcePanel
        v-if="lastSources.length > 0"
        :sources="lastSources"
        @open-source="handleOpenSource"
      />

      <!-- 输入区域 -->
      <InputBar
        :is-busy="isBusy"
        :model-panel-open="uiStore.modelPanelOpen"
        :selected-paper-count="libraryStore.selectedPaperCount"
        @send="handleSend"
        @upload-pdf="handleUploadPdf"
        @toggle-papers="togglePaperPanel"
        @clear-papers="libraryStore.clearSelectedPapers()"
        @toggle-model="uiStore.toggleModelPanel"
        @close-model="uiStore.closeModelPanel"
      />

      <!-- 文献选择弹窗 -->
      <Teleport to="body">
        <div v-if="paperPanelOpen" class="paper-overlay" @click="paperPanelOpen = false">
          <div class="paper-panel" @click.stop>
            <div class="paper-panel-header">
              <h3>选择文献</h3>
              <button class="paper-close-btn" type="button" @click="paperPanelOpen = false">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>

            <div v-if="libraryStore.loading" class="paper-loading">加载中...</div>
            <div v-else-if="libraryStore.error" class="paper-error">{{ libraryStore.error }}</div>
            <div v-else-if="libraryStore.paperCount === 0" class="paper-empty">还没有导入论文</div>
            <div v-else class="paper-list">
              <label
                v-for="paper in libraryStore.papers"
                :key="paper.paper_id"
                class="paper-option"
              >
                <input
                  type="checkbox"
                  :value="paper.paper_id"
                  :checked="libraryStore.selectedPaperIds.includes(paper.paper_id)"
                  @change="libraryStore.togglePaperSelection(paper.paper_id)"
                >
                <span class="paper-option-title">{{ paper.title }}</span>
              </label>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- 历史记录弹窗 -->
      <Teleport to="body">
        <div v-if="historyPanelOpen" class="paper-overlay" @click="historyPanelOpen = false">
          <div class="paper-panel" @click.stop>
            <div class="paper-panel-header">
              <h3>历史记录</h3>
              <button class="paper-close-btn" type="button" @click="historyPanelOpen = false">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div v-if="sessionsLoading" class="paper-empty">加载中...</div>
            <div v-else-if="sessions.length === 0" class="paper-empty">暂无历史记录</div>
            <div v-else class="paper-list">
              <div
                v-for="session in sessions"
                :key="session.session_id"
                class="session-item"
                :class="{ active: session.session_id === store.sessionId }"
                @click="switchToSession(session.session_id)"
              >
                <div class="session-info">
                  <div class="session-title">{{ session.title }}</div>
                  <div class="session-date">{{ formatDate(session.updated_at) }}</div>
                </div>
                <button
                  class="session-delete-btn"
                  type="button"
                  @click.stop="handleDeleteSession(session.session_id)"
                  title="删除此会话"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Teleport>
    </main>

    <!-- 引用悬停预览（全局，带 1s 延迟） -->
    <CitationPreview
      :visible="previewVisible"
      :source="previewSource"
      :x="previewX"
      :y="previewY"
      @preview-enter="cancelHideTimer"
      @preview-leave="startHideTimer"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import type { SourceCard } from '../types/source'
import { useConversationStore } from '../stores/conversation'
import type { ConversationRecord, UserMessage, AssistantMessage } from '../stores/conversation'
import { useLibraryStore } from '../stores/library'
import { useUiStore } from '../stores/ui'
import { listSessions, createSession, deleteSession, getMessages } from '../services/conversation-api'
import type { ConversationSession } from '../services/conversation-api'
import { useWPSPolling } from '../composables/wps'
import TopBar from '../components/TopBar.vue'
import MessageList from '../components/MessageList.vue'
import EmptyState from '../components/EmptyState.vue'
import SourcePanel from '../components/SourcePanel.vue'
import InputBar from '../components/InputBar.vue'
import CitationPreview from '../components/CitationPreview.vue'

const store = useConversationStore()
const libraryStore = useLibraryStore()
const uiStore = useUiStore()

const { startPolling, isWPSAvailable } = useWPSPolling(true, () => store.sessionId)

const messagesContainer = ref<HTMLElement>()
const paperPanelOpen = ref(false)
const historyPanelOpen = ref(false)
const sessions = ref<ConversationSession[]>([])
const sessionsLoading = ref(false)

const isBusy = computed(() => store.status === 'requesting' || store.status === 'thinking' || store.status === 'streaming')

// 最新 assistant 消息的来源
const lastSources = computed<SourceCard[]>(() => {
  const reversed = [...store.messages].reverse()
  const last = reversed.find((m) => m.role === 'assistant')
  if (!last || last.role !== 'assistant') return []
  return last.sources
})

// ─── 引用悬停预览（1s 延迟）───
const previewVisible = ref(false)
const previewSource = ref<SourceCard | null>(null)
const previewX = ref(0)
const previewY = ref(0)
let hoverTimer: ReturnType<typeof setTimeout> | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null

function handleCitationHover(sourceId: string, event: MouseEvent) {
  cancelHoverTimer()
  cancelHideTimer()

  // 1 秒后显示预览
  hoverTimer = setTimeout(() => {
    const src = lastSources.value.find((s) => s.id === sourceId)
    if (!src) return
    previewSource.value = src
    previewX.value = event.clientX
    previewY.value = event.clientY
    previewVisible.value = true
  }, 1000)
}

function handleCitationLeave() {
  cancelHoverTimer()
  startHideTimer()
}

function handleCitationClick(sourceId: string) {
  const src = lastSources.value.find((s) => s.id === sourceId)
  if (!src) return
  handleOpenSource(src)
}

function cancelHoverTimer() {
  if (hoverTimer) {
    clearTimeout(hoverTimer)
    hoverTimer = null
  }
}

function cancelHideTimer() {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function startHideTimer() {
  cancelHideTimer()
  hideTimer = setTimeout(() => {
    previewVisible.value = false
  }, 300)
}

// ─── 发送 ───
async function handleSend(promptText: string) {
  await store.sendPrompt({
    session_id: store.sessionId,
    prompt: promptText,
    paper_ids: libraryStore.selectedPaperIds,
    enable_rag: libraryStore.selectedPaperIds.length > 0,
  })
}

// ─── 新建对话 ───
async function handleNewChat() {
  if (isBusy.value && !confirm('当前对话正在进行中，确定要开始新对话吗？')) return
  try {
    const session = await createSession()
    store.reset()
    store.sessionId = session.session_id
  } catch {
    store.reset()
  }
  libraryStore.clearSelectedPapers()
}

// ─── 历史记录 ───
async function handleOpenHistory() {
  historyPanelOpen.value = !historyPanelOpen.value
  if (historyPanelOpen.value) {
    sessionsLoading.value = true
    try {
      sessions.value = await listSessions()
    } catch {
      sessions.value = []
    } finally {
      sessionsLoading.value = false
    }
  }
}

// ─── 切换到某个会话 ───
async function switchToSession(sessionId: string) {
  try {
    const msgs = await getMessages(sessionId)
    store.reset()
    store.sessionId = sessionId
    const mapped: ConversationRecord[] = []
    for (const msg of msgs) {
      if (msg.role === 'user') {
        mapped.push({
          id: `user-${msg.created_at}`,
          role: 'user',
          content: msg.content,
          createdAt: msg.created_at,
        } as UserMessage)
      } else if (msg.role === 'assistant') {
        mapped.push({
          id: `assistant-${msg.created_at}`,
          role: 'assistant',
          createdAt: msg.created_at,
          thinking: '',
          thinkingTimeMs: 0,
          blocks: [{ type: 'paragraph', text: msg.content }],
          sources: msg.sources_json ? JSON.parse(msg.sources_json) : [],
        } as AssistantMessage)
      }
    }
    store.messages = mapped
  } catch {
    store.reset()
    store.sessionId = sessionId
  }
  historyPanelOpen.value = false
  libraryStore.clearSelectedPapers()
}

// ─── 删除会话 ───
async function handleDeleteSession(sessionId: string) {
  try {
    await deleteSession(sessionId)
    sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
    if (store.sessionId === sessionId) {
      store.reset()
      libraryStore.clearSelectedPapers()
    }
  } catch {
    // 静默失败，保留列表原样
  }
}

// ─── 打开 PDF ───
function handleOpenSource(source: SourceCard) {
  const filePath = source.file_path || source.local_path
  if (!filePath) return

  if (isWPSAvailable.value && window.wps?.OAAssist?.ShellExecute) {
    window.wps.OAAssist.ShellExecute(filePath)
  } else {
    // 浏览器回退：尝试用 file:// 打开
    const fileUrl = filePath.replace(/\\/g, '/')
    window.open(`file:///${fileUrl}`, '_blank')
  }
}

// ─── 上传 PDF ───
async function handleUploadPdf(file: File) {
  await libraryStore.importFile(file)
}

function togglePaperPanel() {
  paperPanelOpen.value = !paperPanelOpen.value
  if (paperPanelOpen.value) {
    libraryStore.loadPapers()
  }
}

// ─── 日期格式化 ───
function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ─── 滚动到底部 ───
function scrollToBottom() {
  nextTick(() => {
    const el = messagesContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

onMounted(() => {
  if (isWPSAvailable.value) startPolling()
})

watch(() => store.messages.length, scrollToBottom)
watch(() => store.status, (s) => {
  if (s === 'streaming' || s === 'done') scrollToBottom()
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--color-surface-base);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 16px 12px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px 0;
  scroll-behavior: smooth;
}

.chat-messages-inner {
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
}

/* 文献选择弹层 */
.paper-overlay {
  position: fixed;
  inset: 0;
  z-index: 150;
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.paper-panel {
  width: 400px;
  max-height: 60vh;
  overflow-y: auto;
  background: var(--color-surface-card);
  border-radius: 14px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15);
  padding: 20px 24px;
}

.paper-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.paper-panel-header h3 {
  font-size: 16px;
  font-weight: 600;
}

.paper-close-btn {
  padding: 4px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--color-text-muted);
}

.paper-close-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.paper-loading, .paper-empty, .paper-error {
  text-align: center;
  padding: 24px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.paper-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.paper-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.1s ease;
}

.paper-option:hover {
  background: var(--color-surface-muted);
}

.paper-option-title {
  font-size: 13px;
  color: var(--color-text-primary);
}

/* 会话列表 */
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.1s ease;
}

.session-item:hover {
  background: var(--color-surface-muted);
}

.session-item.active {
  background: var(--color-surface-muted);
  font-weight: 500;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-date {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.session-delete-btn {
  flex-shrink: 0;
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  color: var(--color-text-muted);
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}

.session-item:hover .session-delete-btn {
  opacity: 1;
}

.session-delete-btn:hover {
  color: var(--color-error, #e53e3e);
  background: var(--color-surface-muted);
}
</style>
