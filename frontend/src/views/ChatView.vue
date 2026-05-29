<template>
  <div class="chat-layout">
    <TopBar @new-chat="handleNewChat" @open-history="handleOpenHistory" />

    <main class="chat-main">
      <!-- 消息区域 -->
      <div class="chat-messages" ref="messagesContainer">
        <div class="chat-messages-inner">
          <Transition name="fade" mode="out-in">
            <MessageList
              v-if="store.messages.length > 0"
              :key="'messages'"
              :messages="store.messages"
              :status="store.status"
              :error-message="store.errorMessage ?? undefined"
              :phase-message="store.phaseMessage"
              @citation-hover="handleCitationHover"
              @citation-leave="handleCitationLeave"
              @citation-click="handleCitationClick"
              @retry="handleRetry"
              @regenerate="handleRegenerate"
              @stop="store.abortStreaming()"
              @delete-message="handleDeleteMessage"
              @resubmit-message="handleResubmitMessage"
              @follow-up="handleFollowUp"
            />
            <EmptyState
              v-else
              :key="'empty-' + resetCounter"
              @select-prompt="handleSelectPrompt"
            />
          </Transition>
        </div>
      </div>

      <!-- 输入区域 -->
      <InputBar
        :is-busy="isBusy"
        :selected-paper-count="libraryStore.selectedPaperCount"
        :selected-paper-names="selectedPaperNames"
        :thinking-enabled="thinkingEnabled"
        @send="handleSend"
        @stop="store.abortStreaming()"
        @upload-pdf="handleUploadPdf"
        @toggle-papers="togglePaperPanel"
        @clear-papers="libraryStore.clearSelectedPapers()"
        @toggle-thinking="thinkingEnabled = !thinkingEnabled"
      />
    </main>

    <!-- 侧栏抽屉 -->
    <SidebarDrawer
      :visible="uiStore.sidebarOpen"
      :active-tab="uiStore.sidebarTab"
      @close="uiStore.closeSidebar()"
      @update:active-tab="(tab: 'history' | 'library') => { uiStore.sidebarTab = tab; if (tab === 'library') libraryStore.loadPapers() }"
    >
      <template #history>
        <HistoryPanel
          :sessions="sessions"
          :loading="sessionsLoading"
          :active-session-id="store.sessionId"
          @select="switchToSession"
          @delete="handleDeleteSession"
        />
      </template>

      <template #library>
        <LibraryPanel
          :papers="libraryStore.papers"
          :loading="libraryStore.loading"
          :error="libraryStore.error"
          :selected-ids="libraryStore.selectedPaperIds"
          @toggle="libraryStore.togglePaperSelection($event)"
          @upload="triggerFileUpload"
          @remove="handleRemovePaper"
          @retry="handleRetryImport"
          @select-all="libraryStore.setSelectedPaperIds($event)"
        />
      </template>
    </SidebarDrawer>

    <!-- 引用悬停预览（全局，带 300ms 延迟） -->
    <CitationPreview
      :visible="previewVisible"
      :source="previewSource"
      :x="previewX"
      :y="previewY"
      @preview-enter="cancelHideTimer"
      @preview-leave="startHideTimer"
      @preview-click="handlePreviewClick"
    />

    <!-- PDF 阅读面板 -->
    <PdfReaderPanel
      :visible="uiStore.readerOpen"
      :paper-id="uiStore.readerPaperId ?? ''"
      :target-page="uiStore.readerTargetPage"
      :highlight-text="uiStore.readerHighlightText ?? undefined"
      :demo-mode="demoActive"
      @close="uiStore.closeReader()"
    />

    <!-- 配置初始化弹窗 -->
    <ConfigInitDialog
      :visible="configDialogVisible"
      @close="configDialogVisible = false"
      @saved="handleConfigSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import type { SourceCard } from '../types/source'
import { useConversationStore } from '../stores/conversation'
import type { ConversationRecord, UserMessage, AssistantMessage } from '../stores/conversation'
import { useLibraryStore } from '../stores/library'
import { useSettingsStore } from '../stores/settings'
import { useUiStore } from '../stores/ui'
import { listSessions, createSession, deleteSession, getMessages } from '../services/conversation-api'

import type { ConversationSession } from '../services/conversation-api'
import { useWPSPolling } from '../composables/wps'
import { isDemoMode, DEMO_PAPERS, DEMO_SESSIONS } from '../demo'
import TopBar from '../components/TopBar.vue'
import MessageList from '../components/MessageList.vue'
import EmptyState from '../components/EmptyState.vue'

import InputBar from '../components/InputBar.vue'
import ConfigInitDialog from '../components/ConfigInitDialog.vue'
import CitationPreview from '../components/CitationPreview.vue'
import PdfReaderPanel from '../components/PdfReaderPanel.vue'
import SidebarDrawer from '../components/SidebarDrawer.vue'
import HistoryPanel from '../components/HistoryPanel.vue'
import LibraryPanel from '../components/LibraryPanel.vue'

const store = useConversationStore()
const libraryStore = useLibraryStore()
const settingsStore = useSettingsStore()
const uiStore = useUiStore()
const resetCounter = ref(0)
const configDialogVisible = ref(false)

const { startPolling, isWPSAvailable } = useWPSPolling(true, () => store.sessionId)

const messagesContainer = ref<HTMLElement>()
const thinkingEnabled = ref(false)
const sessions = ref<ConversationSession[]>([])
const sessionsLoading = ref(false)

const isBusy = computed(() => store.status === 'requesting' || store.status === 'thinking' || store.status === 'streaming')

const selectedPaperNames = computed(() =>
  libraryStore.selectedPaperIds
    .map(id => libraryStore.papers.find(p => p.paper_id === id)?.title)
    .filter(Boolean) as string[]
)

// 所有 assistant 消息的来源（用于引用查找）
const allSources = computed<SourceCard[]>(() => {
  const sources: SourceCard[] = []
  for (const msg of store.messages) {
    if (msg.role === 'assistant') {
      sources.push(...msg.sources)
    }
  }
  return sources
})

// ─── 引用悬停预览（300ms 延迟）───
const previewVisible = ref(false)
const previewSource = ref<SourceCard | null>(null)
const previewX = ref(0)
const previewY = ref(0)
let hoverTimer: ReturnType<typeof setTimeout> | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null

function handleCitationHover(sourceId: string, event: MouseEvent) {
  cancelHoverTimer()
  cancelHideTimer()

  // 300ms 后显示预览
  hoverTimer = setTimeout(() => {
    const src = allSources.value.find((s) => s.id === sourceId)
    if (!src) return
    previewSource.value = src
    previewX.value = event.clientX
    previewY.value = event.clientY
    previewVisible.value = true
  }, 300)
}

function handleCitationLeave() {
  cancelHoverTimer()
  startHideTimer()
}

function handleCitationClick(sourceId: string) {
  const src = allSources.value.find((s) => s.id === sourceId)
  if (!src) return
  // 无 paper_id：显示预览浮窗
  if (!src.paper_id) {
    showCitationPreview(src)
    return
  }
  // WPS 环境（非 demo）：走外部打开
  if (!demoActive.value && isWPSAvailable.value) {
    handleOpenSource(src)
    return
  }
  // 浏览器环境 / demo 模式：打开 PDF 阅读面板
  uiStore.openReader(src.paper_id, src.page)
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
  // Auto-abort if currently busy
  if (isBusy.value) {
    store.abortStreaming()
  }
  // Create backend session on first message (non-demo mode)
  if (!demoActive.value && store.messages.length === 0) {
    try {
      const session = await createSession()
      store.sessionId = session.session_id
    } catch {
      // Fallback to local session ID
    }
  }
  await store.sendPrompt({
    session_id: store.sessionId,
    prompt: promptText,
    paper_ids: libraryStore.selectedPaperIds,
    enable_rag: libraryStore.selectedPaperIds.length > 0,
  })
}

function handleSelectPrompt(promptText: string) {
  handleSend(promptText)
}

// ─── 重试：重新发送最后一条用户消息 ───
function handleRetry() {
  const lastUserMsg = [...store.messages].reverse().find(m => m.role === 'user')
  if (!lastUserMsg) return
  store.sendPrompt({
    session_id: store.sessionId,
    prompt: lastUserMsg.content,
    paper_ids: libraryStore.selectedPaperIds,
    enable_rag: libraryStore.selectedPaperIds.length > 0,
  })
}

// ─── 消息操作 ───
function handleRegenerate(messageId: string) {
  // Find the user message before this AI message
  const idx = store.messages.findIndex(m => m.id === messageId)
  if (idx > 0 && store.messages[idx - 1].role === 'user') {
    store.regenerateAfterUser(store.messages[idx - 1].id)
  }
}

function handleDeleteMessage(messageId: string) {
  const msg = store.messages.find(m => m.id === messageId)
  if (!msg) return
  if (msg.role === 'user') {
    store.deleteMessagePair(messageId)
  } else {
    store.deleteMessage(messageId)
  }
}

async function handleResubmitMessage(messageId: string, newText: string) {
  await store.resubmitMessage(messageId, newText)
}

function handleFollowUp(text: string) {
  const textarea = document.querySelector('.composer-textarea') as HTMLTextAreaElement
  if (textarea) {
    textarea.value = `关于"${text.slice(0, 50)}..."，我想继续了解：`
    textarea.dispatchEvent(new Event('input'))
    textarea.focus()
  }
}

// ─── Demo 模式初始化 ──
const demoActive = ref(isDemoMode())

function initDemoMode() {
  // 加载 mock 论文到 library
  libraryStore.papers = DEMO_PAPERS

  // 加载 mock 会话
  sessions.value = DEMO_SESSIONS.map(s => ({
    session_id: s.session_id,
    title: s.title,
    created_at: s.created_at,
    updated_at: s.created_at,
  }))

  // 默认选中几篇论文
  libraryStore.setSelectedPaperIds(['paper-1', 'paper-2'])
}

// 探测后端是否可达（不依赖文献库是否有数据）
async function probeBackend(): Promise<boolean> {
  try {
    const resp = await fetch('/api/v1/papers', { method: 'HEAD' })
    return resp.ok || resp.status === 405
  } catch {
    return false
  }
}

// ─── 配置保存完成 ───
function handleConfigSaved() {
  configDialogVisible.value = false
  settingsStore.backendConfigured = true
}

// ─── 新建对话 ───
async function handleNewChat() {
  if (isBusy.value && !confirm('当前对话正在进行中，确认开始新对话？')) return
  // Just reset locally — don't create a backend session until user actually sends a message
  store.reset()
  resetCounter.value++
  libraryStore.clearSelectedPapers()
}

// ─── 历史记录 ───
async function handleOpenHistory() {
  uiStore.openSidebar('history')
  if (demoActive.value) {
    return
  }
  sessionsLoading.value = true
  try {
    sessions.value = await listSessions()
  } catch {
    sessions.value = []
  } finally {
    sessionsLoading.value = false
  }
}

// ─── 切换到某个会话 ───
async function switchToSession(sessionId: string) {
  // Demo 模式：从 mock 数据加载
  if (demoActive.value) {
    const demoSession = DEMO_SESSIONS.find(s => s.session_id === sessionId)
    store.reset()
    store.sessionId = sessionId
    if (demoSession) {
      store.messages = [...demoSession.messages]
    }
    uiStore.closeSidebar()
    return
  }

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
  uiStore.closeSidebar()
  libraryStore.clearSelectedPapers()
}

// ─── 删除会话 ───
async function handleDeleteSession(sessionId: string) {
  if (demoActive.value) {
    sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
    if (store.sessionId === sessionId) {
      store.reset()
      libraryStore.clearSelectedPapers()
    }
    return
  }
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
  if (!filePath) {
    showCitationPreview(source)
    return
  }

  if (isWPSAvailable.value && window.wps?.OAAssist?.ShellExecute) {
    window.wps.OAAssist.ShellExecute(filePath)
  } else if (source.paper_id) {
    uiStore.openReader(source.paper_id, source.page)
  } else {
    showCitationPreview(source)
  }
}

// 点击引用预览浮窗 → 打开阅读面板
function handlePreviewClick() {
  const src = previewSource.value
  if (!src) return
  previewVisible.value = false
  if (src.paper_id) {
    uiStore.openReader(src.paper_id, src.page)
  }
}

// 在 citation preview 中展示来源内容（用于 demo 模式或无本地文件时）
function showCitationPreview(source: SourceCard) {
  cancelHoverTimer()
  cancelHideTimer()
  previewSource.value = source
  // Position near center of viewport
  previewX.value = Math.max(window.innerWidth / 2 - 200, 20)
  previewY.value = Math.max(window.innerHeight / 4, 20)
  previewVisible.value = true
}

// ─── 上传 PDF ───
async function handleUploadPdf(file: File) {
  if (demoActive.value) return
  await libraryStore.importFiles([file])
}

function togglePaperPanel() {
  uiStore.openSidebar('library')
  libraryStore.loadPapers()
}

// ─── 文献库上传 ───
function triggerFileUpload() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf'
  input.multiple = true
  input.onchange = async () => {
    const files = input.files
    if (!files || files.length === 0) return
    const pdfFiles = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    await libraryStore.importFiles(pdfFiles)
  }
  input.click()
}

// ─── 文献库移除 ───
async function handleRemovePaper(paperId: string) {
  try {
    await libraryStore.removePaper(paperId)
  } catch {
    // error state managed by the store
  }
}

// ─── 重试失败的导入 ───
async function handleRetryImport(paperId: string) {
  try {
    const { retryImport } = await import('../services/library-api')
    const result = await retryImport(paperId)
    await libraryStore.monitorImportStatus(result.task_id)
    libraryStore.loadPapers()
  } catch (err) {
    console.error('重试导入失败', err)
  }
}

// ─── 滚动到底部 ───
function scrollToBottom() {
  nextTick(() => {
    const el = messagesContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ─── 键盘快捷键 ───
function handleKeydown(e: KeyboardEvent) {
  // Ctrl+K: open sidebar search (history)
  if (e.ctrlKey && e.key === 'k') {
    e.preventDefault()
    uiStore.openSidebar('history')
    return
  }
  // Ctrl+N: new chat
  if (e.ctrlKey && e.key === 'n') {
    e.preventDefault()
    handleNewChat()
    return
  }
}

onMounted(async () => {
  if (demoActive.value) {
    // Explicitly requested demo via ?demo param
    initDemoMode()
  } else {
    // Probe backend — if unreachable, auto-activate demo mode
    const backendOk = await probeBackend()
    if (!backendOk) {
      demoActive.value = true
      initDemoMode()
    } else {
      if (isWPSAvailable.value) startPolling()
      // Verify backend config from server, but trust localStorage to avoid
      // popping the dialog on pages where it shouldn't appear
      const cachedConfigured = localStorage.getItem('backendConfigured') === 'true'
      await settingsStore.fetchBackendConfig()
      if (!settingsStore.backendConfigured && !cachedConfigured) {
        configDialogVisible.value = true
      }
    }
  }
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
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

@media (max-width: 420px) {
  .chat-main {
    padding: 0 var(--space-3) var(--space-2);
  }

  .chat-messages-inner {
    max-width: 100%;
  }
}
</style>
