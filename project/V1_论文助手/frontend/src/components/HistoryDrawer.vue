<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useConversationStore } from '../stores/conversation'
import { useLibraryStore } from '../stores/library'

interface ConversationSummary {
  session_id: string
  msg_count: number
  last_active: string
  preview: string
}

type DrawerSection = 'nav' | 'library'

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'new-chat'): void
}>()

const conversationStore = useConversationStore()
const libraryStore = useLibraryStore()

const currentSection = ref<DrawerSection>('nav')
const fileInputRef = ref<HTMLInputElement>()
const conversationList = ref<ConversationSummary[]>([])
const loadingHistory = ref(false)

const paperCount = computed(() => libraryStore.paperCount)
const filteredPapers = computed(() => libraryStore.filteredPapers)

onMounted(() => {
  loadConversationList()
})

async function loadConversationList() {
  loadingHistory.value = true
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
    const res = await fetch(`${baseUrl}/api/v1/conversations/list?limit=20`)
    if (res.ok) {
      conversationList.value = await res.json()
    }
  } catch {
    // 静默处理
  } finally {
    loadingHistory.value = false
  }
}

async function resumeConversation(sessionId: string) {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
    const res = await fetch(`${baseUrl}/api/v1/conversations/${sessionId}`)
    if (res.ok) {
      const data = await res.json()
      conversationStore.loadHistory(data)
      emit('close')
    }
  } catch {
    // 静默处理
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

function handleNewChat() {
  conversationStore.reset()
  emit('new-chat')
}

function openSection(section: DrawerSection) {
  currentSection.value = section
  if (section === 'library') {
    libraryStore.loadPapers()
  }
}

function goBack() {
  currentSection.value = 'nav'
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    libraryStore.importFile(file)
  }
  input.value = ''
}

function triggerFileSelect() {
  fileInputRef.value?.click()
}

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return `${d.getMonth() + 1}/${d.getDate()}`
  } catch {
    return ''
  }
}

async function confirmDelete(paperId: string) {
  if (!confirm('确定删除这篇论文？此操作不可撤销。')) return
  try {
    await libraryStore.removePaper(paperId)
  } catch {
    // store 已经设置了 error
  }
}
</script>

<template>
  <section class="drawer-page">
    <!-- 主导航 -->
    <section v-if="currentSection === 'nav'" class="nav-page">
      <h1 class="brand-title">论文助手</h1>

      <nav class="nav-menu">
        <button class="nav-link nav-link-accent" type="button" @click="handleNewChat">
          <span class="nav-bubble nav-bubble-accent"><span class="nav-bubble-plus">+</span></span>
          <span class="nav-text">新聊天</span>
        </button>

        <button class="nav-link" type="button" @click="openSection('library')">
          <span class="nav-folder" />
          <span class="nav-text">文献库</span>
          <span class="nav-badge">{{ paperCount }}</span>
        </button>
      </nav>

      <!-- 历史对话 -->
      <section class="history-section">
        <h3 class="history-title">历史对话</h3>
        <div v-if="loadingHistory" class="history-loading">加载中...</div>
        <div v-else-if="conversationList.length === 0" class="history-empty">暂无对话记录</div>
        <div v-else class="history-list">
          <button
            v-for="conv in conversationList"
            :key="conv.session_id"
            class="history-item"
            type="button"
            @click="resumeConversation(conv.session_id)"
          >
            <div class="history-preview">{{ conv.preview || '对话' }}</div>
            <div class="history-meta">
              <span>{{ conv.msg_count }} 条消息</span>
              <span>{{ formatTime(conv.last_active) }}</span>
            </div>
          </button>
        </div>
      </section>
    </section>

    <!-- 文献库 -->
    <section v-else-if="currentSection === 'library'" class="subpage">
      <header class="subpage-topbar">
        <button class="subpage-icon" type="button" aria-label="返回导航" @click="goBack">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        </button>
        <h1 class="subpage-title-small">文献库</h1>
        <button class="subpage-icon" type="button" aria-label="上传 PDF" @click="triggerFileSelect">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf"
          class="file-input-hidden"
          @change="handleFileSelect"
        />
      </header>

      <!-- 导入进度 -->
      <div v-if="libraryStore.importing" class="import-progress">
        <div class="import-header">
          <span class="import-filename">{{ libraryStore.importFileName }}</span>
        </div>
        <div class="progress-bar-wrapper">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: libraryStore.importPercent + '%' }" />
          </div>
          <span class="progress-percent">{{ libraryStore.importPercent }}%</span>
        </div>
        <div class="import-step">{{ libraryStore.importStep }}</div>
      </div>

      <!-- 导入错误 -->
      <div v-if="libraryStore.importError" class="import-error">
        <span>{{ libraryStore.importError }}</span>
        <button class="dismiss-btn" @click="libraryStore.clearImportError()">关闭</button>
      </div>

      <!-- 搜索 -->
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
        />
      </div>

      <!-- 加载中 -->
      <div v-if="libraryStore.loading" class="loading-state">加载中...</div>

      <!-- 错误 -->
      <div v-else-if="libraryStore.error" class="error-state">{{ libraryStore.error }}</div>

      <!-- 空状态 -->
      <div v-else-if="paperCount === 0 && !libraryStore.importing" class="empty-library">
        <p class="empty-text">还没有导入论文</p>
        <button class="upload-btn" @click="triggerFileSelect">上传 PDF</button>
      </div>

      <!-- 论文列表 -->
      <div v-else class="paper-list">
        <div class="paper-stats">共 {{ paperCount }} 篇</div>
        <div
          v-for="paper in filteredPapers"
          :key="paper.paper_id"
          class="paper-card"
        >
          <div class="paper-info">
            <div class="paper-title" :title="paper.title">{{ paper.title }}</div>
            <div class="paper-meta">
              <span v-if="paper.authors">{{ paper.authors }}</span>
              <span>{{ paper.chunk_count }} 块</span>
              <span>{{ formatDate(paper.import_time) }}</span>
            </div>
          </div>
          <button class="delete-btn" @click.stop="confirmDelete(paper.paper_id)" title="删除">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <path d="M5 1h4v1H5zM2 3h10v1H2zM3 4h8v8a1 1 0 01-1 1H4a1 1 0 01-1-1V4z"/>
            </svg>
          </button>
        </div>
        <div v-if="filteredPapers.length === 0 && libraryStore.searchQuery" class="no-results">
          没有匹配的论文
        </div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.drawer-page {
  position: absolute;
  inset: 0;
  background: var(--color-surface-muted);
  z-index: 5;
  overflow-y: auto;
}

.nav-page {
  min-height: 100%;
  display: grid;
  align-content: start;
  padding: 28px 24px 24px;
  gap: 32px;
}

.brand-title {
  color: var(--color-text-primary);
  font-size: 32px;
  line-height: 1;
  font-weight: 700;
}

.nav-menu {
  display: grid;
  gap: 20px;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 16px;
  border: none;
  background: transparent;
  color: #41403b;
  text-align: left;
  cursor: pointer;
  padding: var(--space-2);
  border-radius: var(--radius-md);
  transition: background 0.15s ease;
}

.nav-link:hover {
  background: rgba(0, 0, 0, 0.04);
}

.nav-link-accent {
  color: var(--color-text-primary);
}

.nav-text {
  font-size: 17px;
  line-height: 1.2;
  flex: 1;
}

.nav-badge {
  font-size: 13px;
  color: var(--color-text-secondary);
  padding: 2px 8px;
  background: var(--color-surface-card);
  border-radius: var(--radius-full);
}

.nav-bubble {
  position: relative;
  width: 24px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
}

.nav-bubble-accent {
  border: 2px solid var(--color-text-primary);
}

.nav-bubble-accent::after {
  content: '';
  position: absolute;
  left: 4px;
  bottom: -6px;
  width: 8px;
  height: 8px;
  border-left: 2px solid var(--color-text-primary);
  border-bottom: 2px solid var(--color-text-primary);
  border-radius: 0 0 0 6px;
}

.nav-bubble-plus {
  font-size: 14px;
  line-height: 1;
  font-weight: 700;
}

.nav-folder {
  position: relative;
  width: 22px;
  height: 16px;
  border: 2px solid #47443f;
  border-radius: 4px;
}

.nav-folder::before {
  content: '';
  position: absolute;
  top: -5px;
  left: 2px;
  width: 10px;
  height: 5px;
  border: 2px solid #47443f;
  border-bottom: none;
  border-radius: 4px 4px 0 0;
  background: var(--color-surface-muted);
}

/* ─── 历史对话 ─── */
.history-section {
  display: grid;
  gap: var(--space-3);
}

.history-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.history-loading,
.history-empty {
  font-size: 13px;
  color: var(--color-text-muted);
  text-align: center;
  padding: var(--space-4) 0;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.history-item {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  transition: all 0.15s ease;
}

.history-item:hover {
  background: var(--color-surface-card);
  border-color: var(--color-border-subtle);
}

.history-preview {
  font-size: 13px;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 2px;
}

.history-meta {
  display: flex;
  gap: var(--space-2);
  font-size: 11px;
  color: var(--color-text-muted);
}

/* ─── 子页面通用 ─── */
.subpage {
  min-height: 100%;
  display: grid;
  align-content: start;
  padding: 16px 20px 24px;
  gap: 14px;
}

.subpage-topbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.subpage-title-small {
  flex: 1;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.subpage-icon {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--color-text-primary);
  cursor: pointer;
  transition: background 0.15s ease;
}

.subpage-icon:hover {
  background: rgba(0, 0, 0, 0.06);
}

.file-input-hidden {
  display: none;
}

/* ─── 导入进度 ─── */
.import-progress {
  padding: var(--space-3);
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
}

.import-header {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-bar-wrapper {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--color-border-subtle);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-text-primary);
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

.progress-percent {
  font-size: 11px;
  color: var(--color-text-secondary);
  min-width: 32px;
  text-align: right;
}

.import-step {
  font-size: 11px;
  color: var(--color-text-muted);
}

.import-error {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  background: var(--color-error-bg);
  border: 1px solid var(--color-error-border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-error);
}

.dismiss-btn {
  padding: 2px 8px;
  background: transparent;
  border: 1px solid var(--color-error-border);
  border-radius: 3px;
  font-size: 11px;
  color: var(--color-error);
  cursor: pointer;
}

/* ─── 搜索 ─── */
.search-shell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  background: var(--color-surface-card);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 14px;
  outline: none;
}

.search-input::placeholder {
  color: var(--color-text-muted);
}

/* ─── 论文列表 ─── */
.paper-stats {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.paper-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.paper-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  transition: border-color 0.15s ease;
}

.paper-card:hover {
  border-color: var(--color-border-strong);
}

.paper-info {
  flex: 1;
  min-width: 0;
}

.paper-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 2px;
}

.paper-meta {
  display: flex;
  gap: var(--space-2);
  font-size: 11px;
  color: var(--color-text-muted);
  flex-wrap: wrap;
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
  transition: all 0.15s;
}

.delete-btn:hover {
  color: var(--color-error);
  border-color: var(--color-error-border);
  background: var(--color-error-bg);
}

.loading-state,
.error-state {
  text-align: center;
  padding: 20px 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.error-state {
  color: var(--color-error);
}

.empty-library {
  text-align: center;
  padding: 32px 0;
}

.empty-text {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-3);
}

.upload-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--color-text-primary);
  color: var(--color-user-bubble-text);
  border: none;
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.upload-btn:hover {
  opacity: 0.85;
}

.no-results {
  text-align: center;
  padding: 16px 0;
  color: var(--color-text-muted);
  font-size: 13px;
}
</style>
