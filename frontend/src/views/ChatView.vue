<template>
  <div class="chat-layout">
    <TopNavBar title="论文助手" @new-chat="handleNewChat" @open-history="sessionManager.handleOpenHistory" />

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
              @citation-hover="citationPreview.handleCitationHover"
              @citation-leave="citationPreview.handleCitationLeave"
              @citation-click="citationPreview.handleCitationClick"
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
        :thinking-enabled="settingsStore.thinkingEnabled"
        @send="handleSend"
        @stop="store.abortStreaming()"
        @upload-pdf="handleUploadPdf"
        @toggle-papers="togglePaperPanel"
        @clear-papers="libraryStore.clearSelectedPapers()"
        @toggle-thinking="settingsStore.toggleThinking()"
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
          :sessions="sessionManager.sessions.value"
          :loading="sessionManager.sessionsLoading.value"
          :active-session-id="store.sessionId"
          @select="sessionManager.switchToSession"
          @delete="sessionManager.handleDeleteSession"
        />
      </template>

      <template #library>
        <LibraryPanel
          :papers="libraryStore.papers"
          :loading="libraryStore.loading"
          :error="libraryStore.error"
          :selected-ids="libraryStore.selectedPaperIds"
          @toggle="libraryStore.togglePaperSelection($event)"
          @upload="fileUpload.triggerUpload"
          @remove="handleRemovePaper"
          @retry="handleRetryImport"
          @select-all="libraryStore.setSelectedPaperIds($event)"
        />
      </template>
    </SidebarDrawer>

    <!-- 引用悬停预览（全局，带 300ms 延迟） -->
    <CitationPreview
      :visible="citationPreview.previewVisible.value"
      :source="citationPreview.previewSource.value"
      :x="citationPreview.previewX.value"
      :y="citationPreview.previewY.value"
      @preview-enter="citationPreview.cancelHideTimer"
      @preview-leave="citationPreview.startHideTimer"
      @preview-click="citationPreview.handlePreviewClick"
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { SourceCard } from '../types/source'
import { useConversationStore } from '../stores/conversation'
import { useLibraryStore } from '../stores/library'
import { useSettingsStore } from '../stores/settings'
import { useUiStore } from '../stores/ui'
import { useWPSPolling } from '../composables/wps'
import { useCitationPreview } from '../composables/use-citation-preview'
import { useSessionManager } from '../composables/use-session-manager'
import { useAutoScroll } from '../composables/use-auto-scroll'
import { useFileUpload } from '../composables/use-file-upload'
import { isDemoMode, DEMO_PAPERS } from '../demo'
import { createSession } from '../services/conversation-api'
import TopNavBar from '../components/TopNavBar.vue'
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

const { startPolling, isWPSAvailable } = useWPSPolling(true, () => store.sessionId)

const resetCounter = ref(0)
const configDialogVisible = ref(false)

// ─── Demo 模式 ───
const demoActive = ref(isDemoMode())

async function initDemoMode() {
  libraryStore.papers = DEMO_PAPERS
  const { DEMO_SESSIONS: demoSessions } = await import('../demo')
  sessionManager.sessions.value = demoSessions.map(s => ({
    session_id: s.session_id,
    title: s.title,
    created_at: s.created_at,
    updated_at: s.created_at,
  }))
  libraryStore.setSelectedPaperIds(['paper-1', 'paper-2'])
}

async function probeBackend(): Promise<boolean> {
  try {
    const resp = await fetch('/api/v1/papers', { method: 'HEAD' })
    return resp.ok || resp.status === 405
  } catch {
    return false
  }
}

// ─── Composables ───
const isBusy = computed(() => store.status === 'requesting' || store.status === 'thinking' || store.status === 'streaming')

const selectedPaperNames = computed(() =>
  libraryStore.selectedPaperIds
    .map(id => libraryStore.papers.find(p => p.paper_id === id)?.title)
    .filter(Boolean) as string[]
)

const allSources = computed<SourceCard[]>(() => {
  const sources: SourceCard[] = []
  for (const msg of store.messages) {
    if (msg.role === 'assistant') {
      sources.push(...msg.sources)
    }
  }
  return sources
})

const citationPreview = useCitationPreview({
  allSources,
  isWPSAvailable,
  openReader: (paperId, page) => uiStore.openReader(paperId, page),
  demoActive,
})

const sessionManager = useSessionManager({
  store,
  libraryStore,
  uiStore,
  demoActive,
})

const { containerRef: messagesContainer } = useAutoScroll(
  () => store.messages.length,
  () => store.status,
)

const fileUpload = useFileUpload({
  accept: '.pdf',
  multiple: true,
  onFiles: async (files) => {
    const pdfFiles = files.filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    await libraryStore.importFiles(pdfFiles)
  },
})

// ─── 发送 ───
async function handleSend(promptText: string) {
  if (isBusy.value) {
    store.abortStreaming()
  }
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

// ─── 重试 ───
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

// ─── 配置保存 ───
function handleConfigSaved() {
  configDialogVisible.value = false
  settingsStore.backendConfigured = true
}

// ─── 新建对话 ───
async function handleNewChat() {
  if (isBusy.value && !confirm('当前对话正在进行中，确认开始新对话？')) return
  store.reset()
  resetCounter.value++
  libraryStore.clearSelectedPapers()
}

// ─── 上传 PDF ───
async function handleUploadPdf(files: File[]) {
  if (demoActive.value) return
  await libraryStore.importFiles(files)
}

function togglePaperPanel() {
  uiStore.openSidebar('library')
  libraryStore.loadPapers()
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
// 后端无 retry 接口，触发文件选择器让用户重新上传
function handleRetryImport(_paperId: string) {
  fileUpload.triggerUpload()
}

// ─── 键盘快捷键 ───
function handleKeydown(e: KeyboardEvent) {
  if (e.ctrlKey && e.key === 'k') {
    e.preventDefault()
    uiStore.openSidebar('history')
    return
  }
  if (e.ctrlKey && e.key === 'n') {
    e.preventDefault()
    handleNewChat()
    return
  }
}

onMounted(async () => {
  if (demoActive.value) {
    initDemoMode()
  } else {
    const backendOk = await probeBackend()
    if (!backendOk) {
      demoActive.value = true
      initDemoMode()
    } else {
      if (isWPSAvailable.value) startPolling()
      await settingsStore.fetchBackendConfig()
      if (!settingsStore.backendConfigured && !sessionStorage.getItem('configDialogShown')) {
        configDialogVisible.value = true
        sessionStorage.setItem('configDialogShown', 'true')
      }
    }
  }
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
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
