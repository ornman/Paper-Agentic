<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useConversationStore } from './stores/conversation'
import { useLibraryStore } from './stores/library'
import { useUiStore } from './stores/ui'
import TopNavBar from './components/TopNavBar.vue'
import HistoryDrawer from './components/HistoryDrawer.vue'
import MessageList from './components/MessageList.vue'
import EmptyState from './components/EmptyState.vue'

const store = useConversationStore()
const libraryStore = useLibraryStore()
const uiStore = useUiStore()

const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement>()
const messagesContainer = ref<HTMLElement>()
const dragActive = ref(false)

const isBusy = computed(() => store.status === 'requesting' || store.status === 'streaming')
const canSend = computed(() => inputText.value.trim().length > 0 && !isBusy.value)
const hasMessages = computed(() => store.messages.length > 0)
const drawerOpen = computed(() => uiStore.historyDrawerOpen || uiStore.libraryDrawerOpen)

async function handleSend() {
  if (!canSend.value) return

  const query = inputText.value.trim()
  inputText.value = ''

  await store.sendPrompt({
    session_id: store.sessionId,
    prompt: query,
  })
}

function handleKeydown(event: KeyboardEvent) {
  const nativeEvent = event as KeyboardEvent & { isComposing?: boolean; keyCode?: number }
  if (nativeEvent.isComposing || nativeEvent.keyCode === 229) return
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  handleSend()
}

function handleNewChat() {
  if (isBusy.value) {
    if (!confirm('当前对话正在进行中，确定要开始新对话吗？')) return
  }
  store.reset()
  uiStore.closeAllDrawers()
}

function handleOpenHistory() {
  uiStore.openHistoryDrawer()
}

function handleCloseDrawer() {
  uiStore.closeAllDrawers()
}

// ─── 拖拽上传 ───
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

async function handleDrop(event: DragEvent) {
  event.preventDefault()
  dragActive.value = false
  const files = event.dataTransfer?.files
  if (files?.[0] && files[0].name.toLowerCase().endsWith('.pdf')) {
    uiStore.openHistoryDrawer()
    await nextTick()
    libraryStore.importFile(files[0])
  }
}

// ─── 自动滚动 ───
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => store.messages.length, () => {
  scrollToBottom()
}, { flush: 'post' })

watch(() => store.status, (s) => {
  if (s === 'streaming' || s === 'done') {
    scrollToBottom()
  }
})
</script>

<template>
  <div
    class="app-shell"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <!-- 拖拽覆盖层 -->
    <div v-if="dragActive" class="drag-overlay">
      <div class="drag-content">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
        <span>松开以导入 PDF</span>
      </div>
    </div>

    <div class="sidebar-container">
      <!-- 顶部导航栏 -->
      <TopNavBar
        v-if="!drawerOpen"
        @open-history="handleOpenHistory"
        @new-chat="handleNewChat"
      />

      <!-- 历史对话 / 文献库抽屉 -->
      <HistoryDrawer
        v-if="drawerOpen"
        @close="handleCloseDrawer"
        @new-chat="handleNewChat"
      />

      <!-- 消息区域 -->
      <main v-if="!drawerOpen" class="sidebar-main">
        <div class="sidebar-content" ref="messagesContainer">
          <div v-if="store.errorMessage" class="conversation-error" role="alert">
            {{ store.errorMessage }}
          </div>
          <MessageList
            v-if="hasMessages"
            :messages="store.messages"
            :status="store.status"
          />
          <EmptyState v-else />
        </div>
      </main>

      <!-- 底部输入栏 -->
      <footer v-if="!drawerOpen" class="bottom-bar">
        <div class="composer-card">
          <textarea
            ref="inputRef"
            v-model="inputText"
            class="composer-input"
            rows="2"
            placeholder="输入您的问题..."
            :disabled="isBusy"
            @keydown="handleKeydown"
          />
          <div class="composer-toolbar">
            <div class="composer-spacer" />
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
      </footer>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  width: 100%;
  height: 100%;
  min-height: 100vh;
  background: #ffffff;
  color: var(--color-text-primary);
  position: relative;
}

/* ─── 拖拽覆盖层 ─── */
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
  padding: var(--space-6) var(--space-6);
  border: 2px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  color: var(--color-text-primary);
  font-size: 16px;
  font-weight: 500;
}

.sidebar-container {
  position: relative;
  display: grid;
  grid-template-rows: auto 1fr auto;
  width: 100%;
  max-width: 100%;
  min-height: 100vh;
  padding: var(--space-3);
  background: var(--color-surface-base);
  overflow: hidden;
}

/* ─── 消息区域 ─── */
.sidebar-main {
  min-height: 0;
  padding-top: var(--space-2);
}

.sidebar-content {
  height: 100%;
  display: grid;
  align-content: start;
  gap: var(--space-5);
  padding: 0 var(--space-1) var(--space-1);
  overflow-y: auto;
  overflow-x: hidden;
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

/* ─── 底部输入栏 ─── */
.bottom-bar {
  position: sticky;
  bottom: 0;
  padding: var(--space-2) 0 var(--space-3);
  background: var(--color-surface-muted);
}

.composer-card {
  width: 100%;
  padding: var(--space-4) 18px 18px;
  border: 1px solid var(--composer-border);
  border-radius: 32px;
  background: var(--composer-surface);
}

.composer-input {
  width: 100%;
  min-height: 52px;
  max-height: 110px;
  resize: none;
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  line-height: 1.55;
  font-size: 15px;
  outline: none;
}

.composer-input::placeholder {
  color: var(--color-text-secondary);
}

.composer-input:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.composer-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.composer-spacer {
  flex: 1;
}

.send-button {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: var(--color-text-primary);
  color: var(--color-user-bubble-text);
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.send-button:hover:not(:disabled) {
  opacity: 0.85;
}

.send-button:active:not(:disabled) {
  transform: scale(0.95);
}

.send-button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
