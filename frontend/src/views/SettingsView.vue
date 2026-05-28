<template>
  <div class="settings-layout">
    <header class="settings-topbar">
      <router-link to="/" class="settings-back-btn">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        返回
      </router-link>
      <h1 class="settings-title">设置与历史</h1>
    </header>

    <main class="settings-main">
      <!-- API 配置卡片 -->
      <section class="settings-card">
        <h2 class="settings-section-title">API 配置</h2>
        <div class="settings-field">
          <label>API Key</label>
          <input v-model="settingsStore.apiKey" type="password" placeholder="sk-..." autocomplete="off">
        </div>
        <div class="settings-field">
          <label>API URL</label>
          <input v-model="settingsStore.apiUrl" type="text" placeholder="https://api.deepseek.com/v1">
        </div>
        <div class="settings-field">
          <label>当前模型</label>
          <input v-model="settingsStore.selectedModel" type="text" placeholder="deepseek-chat">
        </div>
        <div class="settings-field-row">
          <span>思考模式</span>
          <button class="toggle-btn" :class="{ active: settingsStore.thinkingEnabled }" @click="settingsStore.toggleThinking()">
            <span class="toggle-knob"></span>
          </button>
        </div>
      </section>

      <!-- 历史会话卡片 -->
      <section class="settings-card">
        <h2 class="settings-section-title">历史会话</h2>
        <div v-if="loadingHistory" class="settings-empty">加载中...</div>
        <div v-else-if="conversations.length === 0" class="settings-empty">暂无历史会话</div>
        <div v-else class="history-list">
          <div
            v-for="conv in conversations"
            :key="conv.session_id"
            class="history-item"
          >
            <div class="history-item-main">
              <div class="history-item-preview">{{ conv.title || '对话' }}</div>
              <div class="history-item-meta">
                <span>{{ formatTime(conv.updated_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 文献库卡片 -->
      <section class="settings-card">
        <h2 class="settings-section-title">
          文献库
          <span class="paper-count-badge">{{ libraryStore.paperCount }} 篇</span>
        </h2>

        <div v-if="libraryStore.importing" class="import-status">
          <div class="import-status-name">{{ libraryStore.importFileName }}</div>
          <div class="import-status-bar">
            <div class="import-status-fill" :style="{ width: libraryStore.importPercent + '%' }"></div>
          </div>
          <div class="import-status-step">{{ libraryStore.importStep }}</div>
        </div>

        <div v-if="libraryStore.importError" class="import-error-msg">
          {{ libraryStore.importError }}
        </div>

        <div v-if="libraryStore.loading" class="settings-empty">加载中...</div>
        <div v-else-if="libraryStore.paperCount === 0" class="settings-empty">还没有导入论文</div>
        <div v-else class="paper-list">
          <div
            v-for="paper in libraryStore.papers"
            :key="paper.paper_id"
            class="paper-item"
          >
            <div class="paper-item-info">
              <div class="paper-item-title">{{ paper.title }}</div>
              <div class="paper-item-meta">
                <span v-if="paper.authors">{{ paper.authors }}</span>
                <span v-if="paper.chunk_count">{{ paper.chunk_count }} 块</span>
                <span v-if="paper.total_pages">{{ paper.total_pages }} 页</span>
                <span>{{ formatTime(paper.import_time) }}</span>
              </div>
            </div>
            <button
              class="paper-delete-btn"
              type="button"
              @click="handleDeletePaper(paper.paper_id, paper.title, paper.chunk_count)"
            >
              删除
            </button>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useLibraryStore } from '../stores/library'
import { listSessions, type ConversationSession } from '../services/conversation-api'

const settingsStore = useSettingsStore()
const libraryStore = useLibraryStore()

const conversations = ref<ConversationSession[]>([])
const loadingHistory = ref(false)

onMounted(() => {
  loadConversations()
  libraryStore.loadPapers()
})

async function loadConversations() {
  loadingHistory.value = true
  try {
    conversations.value = await listSessions()
  } catch {
    // 静默
  } finally {
    loadingHistory.value = false
  }
}

async function handleDeletePaper(paperId: string, title: string, chunkCount: number) {
  if (!confirm(`删除《${title}》及其 ${chunkCount} 个文本块？此操作不可恢复。`)) return
  try {
    await libraryStore.removePaper(paperId)
  } catch {
    // 静默
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
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return ''
  }
}
</script>

<style scoped>
.settings-layout {
  min-height: 100vh;
  background: var(--color-surface-base);
}

.settings-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--color-surface-card);
  border-bottom: 1px solid var(--color-border-subtle);
}

.settings-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  text-decoration: none;
  transition: background 0.15s ease;
}

.settings-back-btn:hover {
  background: var(--color-surface-muted);
}

.settings-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.settings-main {
  max-width: 640px;
  margin: 0 auto;
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-card {
  padding: 20px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: 14px;
}

.settings-section-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 14px;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.paper-count-badge {
  font-size: 12px;
  font-weight: 400;
  color: var(--color-text-muted);
}

.settings-field {
  margin-bottom: 12px;
}

.settings-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.settings-field input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-primary);
  background: var(--color-surface-base);
  outline: none;
  transition: border-color 0.15s;
}

.settings-field input:focus {
  border-color: var(--color-accent);
}

.settings-field-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  font-size: 13px;
  color: var(--color-text-primary);
}

.toggle-btn {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: var(--color-border-strong);
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
}

.toggle-btn.active {
  background: var(--color-accent);
}

.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  transition: left 0.2s;
}

.toggle-btn.active .toggle-knob {
  left: 22px;
}

.settings-empty {
  text-align: center;
  padding: 24px;
  font-size: 13px;
  color: var(--color-text-muted);
}

/* 历史列表 */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  transition: background 0.1s;
}

.history-item:hover {
  background: var(--color-surface-muted);
}

.history-item-main {
  flex: 1;
}

.history-item-preview {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item-meta {
  display: flex;
  gap: 6px;
  margin-top: 2px;
  font-size: 11px;
  color: var(--color-text-muted);
}

/* 文献列表 */
.paper-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.paper-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  transition: background 0.1s;
}

.paper-item:hover {
  background: var(--color-surface-muted);
}

.paper-item-info {
  flex: 1;
  min-width: 0;
}

.paper-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-item-meta {
  display: flex;
  gap: 8px;
  margin-top: 2px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.paper-delete-btn {
  padding: 4px 10px;
  font-size: 12px;
  color: #d32f2f;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
}

.paper-delete-btn:hover {
  background: rgba(211, 47, 47, 0.08);
}

/* 导入状态 */
.import-status {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: var(--color-surface-muted);
  border-radius: 8px;
}

.import-status-name {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
}

.import-status-bar {
  height: 4px;
  background: var(--color-border-subtle);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}

.import-status-fill {
  height: 100%;
  background: var(--color-accent);
  border-radius: 2px;
  transition: width 0.3s;
}

.import-status-step {
  font-size: 11px;
  color: var(--color-text-muted);
}

.import-error-msg {
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #d32f2f;
  background: rgba(211, 47, 47, 0.06);
  border-radius: 8px;
}
</style>
