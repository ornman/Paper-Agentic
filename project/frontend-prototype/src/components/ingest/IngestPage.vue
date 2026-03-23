<script setup lang="ts">
import { ref } from 'vue'
import { useMockStore, type MockDocument } from '../../stores/mockStore'

const store = useMockStore()
const pdfPath = ref('')
const isImporting = ref(false)
const currentProgress = ref(0)

function handleImport() {
  if (!pdfPath.value.trim()) return

  isImporting.value = true
  currentProgress.value = 0

  // 模拟导入进度
  const interval = setInterval(() => {
    currentProgress.value += 5
    if (currentProgress.value >= 100) {
      clearInterval(interval)
      // 添加到文档列表
      const newDoc: MockDocument = {
        id: Date.now().toString(),
        name: pdfPath.value.split('/').pop() || pdfPath.value,
        path: pdfPath.value,
        pages: Math.floor(Math.random() * 50) + 10,
        status: 'completed',
        progress: 100
      }
      store.documents.push(newDoc)
      pdfPath.value = ''
      isImporting.value = false
    }
  }, 100)
}

function getStatusText(status: MockDocument['status']): string {
  const map = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    error: '错误'
  }
  return map[status]
}
</script>

<template>
  <div class="ingest-page">
    <!-- 导入区域 -->
    <div class="import-section">
      <h3>导入 PDF 文档</h3>
      <div class="input-group">
        <input
          v-model="pdfPath"
          type="text"
          placeholder="输入 PDF 文件路径，如：D:/papers/example.pdf"
          :disabled="isImporting"
        />
        <button
          @click="handleImport"
          :disabled="!pdfPath.trim() || isImporting"
          class="btn-primary"
        >
          {{ isImporting ? '导入中...' : '导入' }}
        </button>
      </div>

      <!-- 进度条 -->
      <div v-if="isImporting" class="progress-bar">
        <div class="progress-fill" :style="{ width: currentProgress + '%' }"></div>
        <span class="progress-text">{{ currentProgress }}%</span>
      </div>
    </div>

    <!-- 文档列表 -->
    <div class="doc-list">
      <h3>已导入文档 ({{ store.documents.length }})</h3>
      <div class="doc-items">
        <div v-for="doc in store.documents" :key="doc.id" class="doc-item">
          <div class="doc-icon">📄</div>
          <div class="doc-info">
            <div class="doc-name">{{ doc.name }}</div>
            <div class="doc-meta">
              <span>{{ doc.pages }} 页</span>
              <span :class="['status', doc.status]">{{ getStatusText(doc.status) }}</span>
            </div>
          </div>
        </div>
        <div v-if="store.documents.length === 0" class="empty-state">
          暂无导入的文档
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ingest-page {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
}

.import-section {
  background: var(--bg-sidebar);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.import-section h3 {
  margin-bottom: 16px;
  font-size: 16px;
}

.input-group {
  display: flex;
  gap: 12px;
}

.input-group input {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
}

.input-group input:focus {
  outline: none;
  border-color: var(--primary);
}

.btn-primary {
  padding: 10px 20px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.progress-bar {
  margin-top: 16px;
  height: 24px;
  background: var(--bg-input);
  border-radius: 12px;
  position: relative;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  transition: width 0.1s;
}

.progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: 500;
}

.doc-list {
  background: var(--bg-sidebar);
  border-radius: 8px;
  padding: 20px;
}

.doc-list h3 {
  margin-bottom: 16px;
  font-size: 16px;
}

.doc-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-input);
  border-radius: 6px;
}

.doc-icon {
  font-size: 24px;
}

.doc-info {
  flex: 1;
}

.doc-name {
  font-size: 14px;
  margin-bottom: 4px;
}

.doc-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.status.completed {
  background: rgba(16, 163, 127, 0.2);
  color: var(--success);
}

.status.processing {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.status.error {
  background: rgba(239, 68, 68, 0.2);
  color: var(--error);
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
</style>
