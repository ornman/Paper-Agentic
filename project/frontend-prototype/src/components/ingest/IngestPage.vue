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

  const interval = setInterval(() => {
    currentProgress.value += 5
    if (currentProgress.value >= 100) {
      clearInterval(interval)
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

function getStatusClass(status: MockDocument['status']): string {
  return `status-${status}`
}
</script>

<template>
  <div class="ingest-page">
    <!-- 导入区域 -->
    <div class="import-section">
      <h3>
        <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14,2 14,8 20,8"/>
          <line x1="12" y1="18" x2="12" y2="12"/>
          <line x1="9" y1="15" x2="15" y2="15"/>
        </svg>
        导入 PDF 文档
      </h3>
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
          <svg v-if="!isImporting" class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17,8 12,3 7,8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <svg v-else class="btn-icon spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
          </svg>
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
      <h3>
        <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        已导入文档
        <span class="count">{{ store.documents.length }}</span>
      </h3>
      <div class="doc-items">
        <div v-for="doc in store.documents" :key="doc.id" class="doc-item">
          <div class="doc-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14,2 14,8 20,8"/>
            </svg>
          </div>
          <div class="doc-info">
            <div class="doc-name">{{ doc.name }}</div>
            <div class="doc-meta">
              <span>{{ doc.pages }} 页</span>
              <span :class="['status-badge', getStatusClass(doc.status)]">
                {{ doc.status === 'completed' ? '已就绪' : doc.status === 'processing' ? '处理中' : '等待中' }}
              </span>
            </div>
          </div>
        </div>
        <div v-if="store.documents.length === 0" class="empty-state">
          <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
            <polyline points="13,2 13,9 20,9"/>
          </svg>
          <p>暂无导入的文档</p>
          <span>输入 PDF 路径开始导入</span>
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

.import-section,
.doc-list {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid var(--border);
}

h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-icon {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.count {
  margin-left: auto;
  background: var(--primary);
  color: white;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}

.input-group {
  display: flex;
  gap: 10px;
}

.input-group input {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 13px;
  transition: border-color 0.2s;
}

.input-group input:focus {
  outline: none;
  border-color: var(--primary);
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: translateY(-1px);
}

.btn-primary:active:not(:disabled) {
  transform: translateY(0);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

.btn-icon.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-bar {
  margin-top: 16px;
  height: 6px;
  background: var(--bg-input);
  border-radius: 3px;
  position: relative;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--primary-light));
  border-radius: 3px;
  transition: width 0.1s;
}

.progress-text {
  position: absolute;
  right: 0;
  top: -20px;
  font-size: 11px;
  color: var(--primary);
  font-weight: 600;
}

.doc-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-input);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.doc-item:hover {
  background: rgba(13, 148, 136, 0.08);
}

.doc-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 148, 136, 0.1);
  border-radius: 8px;
}

.doc-icon svg {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.doc-info {
  flex: 1;
  min-width: 0;
}

.doc-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.status-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.status-completed {
  background: rgba(13, 148, 136, 0.15);
  color: var(--success);
}

.status-processing {
  background: rgba(245, 158, 11, 0.15);
  color: var(--warning);
}

.status-pending {
  background: rgba(100, 116, 139, 0.15);
  color: #64748B;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 16px;
  color: var(--text-secondary);
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 12px;
  opacity: 0.4;
}

.empty-state p {
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.empty-state span {
  font-size: 12px;
}
</style>
