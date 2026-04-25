<template>
  <div class="library-view">
    <!-- 导入进度 -->
    <ImportProgress />

    <!-- 搜索和上传 -->
    <div class="toolbar">
      <div class="search-wrapper">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="#999">
          <circle cx="7" cy="7" r="5" stroke="#999" stroke-width="1.5" fill="none"/>
          <line x1="11" y1="11" x2="14" y2="14" stroke="#999" stroke-width="1.5"/>
        </svg>
        <input
          v-model="store.searchQuery"
          class="search-input"
          placeholder="搜索论文标题或作者..."
          type="text"
        />
      </div>
      <label class="upload-btn" :class="{ disabled: store.importing }">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 1v9M4 5l4-4 4 4M2 12v2h12v-2"/>
        </svg>
        <span>上传 PDF</span>
        <input
          type="file"
          accept=".pdf"
          class="file-input"
          :disabled="store.importing"
          @change="handleFileSelect"
        />
      </label>
    </div>

    <!-- 论文统计 -->
    <div class="stats">
      共 {{ store.paperCount }} 篇论文
      <span v-if="store.searchQuery && store.filteredPapers.length !== store.paperCount">
        ，匹配 {{ store.filteredPapers.length }} 篇
      </span>
    </div>

    <!-- 加载中 -->
    <div v-if="store.loading" class="loading-state">加载中...</div>

    <!-- 错误提示 -->
    <div v-else-if="store.error" class="error-state">{{ store.error }}</div>

    <!-- 空状态 -->
    <div v-else-if="store.paperCount === 0" class="empty-state">
      <div class="empty-icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#b3b3b3" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>
      </div>
      <div class="empty-text">还没有导入论文</div>
      <div class="empty-hint">点击上方"上传 PDF"按钮开始导入</div>
    </div>

    <!-- 论文列表 -->
    <div v-else class="paper-list">
      <div
        v-for="paper in store.filteredPapers"
        :key="paper.paper_id"
        class="paper-card"
      >
        <div class="paper-info">
          <div class="paper-title" :title="paper.title">{{ paper.title }}</div>
          <div class="paper-meta">
            <span v-if="paper.authors">{{ paper.authors }}</span>
            <span>{{ paper.chunk_count }} 块</span>
            <span v-if="paper.total_pages">{{ paper.total_pages }} 页</span>
            <span>{{ formatDate(paper.import_time) }}</span>
          </div>
        </div>
        <button
          class="delete-btn"
          @click="confirmDelete(paper)"
          title="删除"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
            <path d="M5 1h4v1H5zM2 3h10v1H2zM3 4h8v8a1 1 0 01-1 1H4a1 1 0 01-1-1V4z"/>
          </svg>
        </button>
      </div>

      <div v-if="store.filteredPapers.length === 0" class="no-results">
        没有匹配的论文
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <DeleteConfirm
      :visible="deleteTarget !== null"
      :paper-title="deleteTarget?.title ?? ''"
      :chunk-count="deleteTarget?.chunk_count ?? 0"
      :deleting="deleting"
      @confirm="doDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useLibraryStore } from '../stores/library'
import type { PaperItem } from '../services/library-api'
import ImportProgress from '../components/ImportProgress.vue'
import DeleteConfirm from '../components/DeleteConfirm.vue'

const store = useLibraryStore()
const deleteTarget = ref<PaperItem | null>(null)
const deleting = ref(false)

onMounted(() => {
  store.loadPapers()
})

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files ? Array.from(input.files) : []
  if (files.length > 0) {
    try {
      await store.importFiles(files)
    } catch {
    }
  }
  input.value = ''
}

function confirmDelete(paper: PaperItem) {
  deleteTarget.value = paper
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await store.removePaper(deleteTarget.value.paper_id)
    deleteTarget.value = null
  } finally {
    deleting.value = false
  }
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
</script>

<style scoped>
.library-view {
  display: flex;
  flex-direction: column;
  gap: var(--claude-spacing-md);
  flex: 1;
  overflow: hidden;
}

.toolbar {
  display: flex;
  gap: var(--claude-spacing-md);
  align-items: center;
}

.search-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: var(--claude-spacing-sm) var(--claude-spacing-md) var(--claude-spacing-sm) 32px;
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  font-size: 13px;
  outline: none;
  background: var(--claude-bg-card);
  color: var(--claude-text-primary);
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--claude-primary);
}

.upload-btn {
  display: flex;
  align-items: center;
  gap: var(--claude-spacing-xs);
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  background: var(--claude-primary);
  border: none;
  border-radius: var(--claude-radius-md);
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.upload-btn:hover:not(.disabled) {
  background: var(--claude-primary-hover);
}

.upload-btn.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.file-input {
  display: none;
}

.stats {
  font-size: 13px;
  color: var(--claude-text-secondary);
}

.loading-state,
.error-state {
  text-align: center;
  padding: 40px 0;
  color: var(--claude-text-muted);
  font-size: 14px;
}

.error-state {
  color: var(--claude-error);
}

.empty-state {
  text-align: center;
  padding: 40px 0;
}

.empty-icon {
  font-size: 32px;
  margin-bottom: var(--claude-spacing-sm);
}

.empty-text {
  font-size: 15px;
  color: var(--claude-text-secondary);
  margin-bottom: var(--claude-spacing-xs);
}

.empty-hint {
  font-size: 13px;
  color: var(--claude-text-muted);
}

.paper-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--claude-spacing-sm);
}

.paper-card {
  display: flex;
  align-items: center;
  gap: var(--claude-spacing-sm);
  padding: var(--claude-spacing-md);
  background: var(--claude-bg-card);
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  transition: all 0.2s ease;
}

.paper-card:hover {
  box-shadow: var(--claude-shadow-md);
  border-color: var(--claude-primary-light);
}

.paper-info {
  flex: 1;
  min-width: 0;
}

.paper-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--claude-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: var(--claude-spacing-xs);
}

.paper-meta {
  display: flex;
  gap: var(--claude-spacing-sm);
  font-size: 12px;
  color: var(--claude-text-muted);
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
  border-radius: var(--claude-radius-sm);
  color: var(--claude-text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.delete-btn:hover {
  color: var(--claude-error);
  border-color: #F5C6C0;
  background: #FFF5F3;
}

.no-results {
  text-align: center;
  padding: 20px 0;
  color: var(--claude-text-muted);
  font-size: 13px;
}
</style>
