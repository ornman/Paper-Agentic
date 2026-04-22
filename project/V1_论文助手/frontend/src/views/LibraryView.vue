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
      <div class="empty-icon">📚</div>
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

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  store.importFile(file)
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
  flex: 1;
  overflow: hidden;
  padding: 12px 16px;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
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
  padding: 8px 12px 8px 32px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: #6aae6a;
}

.upload-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  background: #6aae6a;
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.2s;
}

.upload-btn:hover:not(.disabled) {
  background: #5a9e5a;
}

.upload-btn.disabled {
  background: #a0c8a0;
  cursor: not-allowed;
}

.file-input {
  display: none;
}

.stats {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.loading-state,
.error-state {
  text-align: center;
  padding: 40px 0;
  color: #999;
  font-size: 14px;
}

.error-state {
  color: #ff4d4f;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
}

.empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 15px;
  color: #666;
  margin-bottom: 4px;
}

.empty-hint {
  font-size: 13px;
  color: #999;
}

.paper-list {
  flex: 1;
  overflow-y: auto;
}

.paper-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: white;
  border: 1px solid #eee;
  border-radius: 8px;
  margin-bottom: 8px;
  transition: border-color 0.2s;
}

.paper-card:hover {
  border-color: #c8e6c8;
}

.paper-info {
  flex: 1;
  min-width: 0;
}

.paper-title {
  font-size: 14px;
  font-weight: 500;
  color: #1a1a1a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.paper-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #999;
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
  border-radius: 4px;
  color: #ccc;
  cursor: pointer;
  transition: all 0.2s;
}

.delete-btn:hover {
  color: #ff4d4f;
  border-color: #ffccc7;
  background: #fff2f0;
}

.no-results {
  text-align: center;
  padding: 20px 0;
  color: #999;
  font-size: 13px;
}
</style>
