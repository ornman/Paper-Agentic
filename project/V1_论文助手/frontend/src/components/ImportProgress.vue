<template>
  <div v-if="store.importing || store.importError" class="import-progress">
    <div class="import-header">
      <span class="import-icon">📄</span>
      <span class="import-filename">{{ store.importFileName }}</span>
    </div>

    <div v-if="store.importing" class="progress-bar-wrapper">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: store.importPercent + '%' }" />
      </div>
      <span class="progress-percent">{{ store.importPercent }}%</span>
    </div>

    <div class="import-step">{{ store.importStep }}</div>

    <div v-if="store.importError" class="import-error">
      <span>{{ store.importError }}</span>
      <button class="dismiss-btn" @click="store.clearImportError()">关闭</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useLibraryStore } from '../stores/library'
const store = useLibraryStore()
</script>

<style scoped>
.import-progress {
  padding: 12px 16px;
  background: #f0f9f0;
  border: 1px solid #c8e6c8;
  border-radius: 8px;
  margin-bottom: 12px;
}

.import-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
}

.import-filename {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: #e0e0e0;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #6aae6a;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-percent {
  font-size: 12px;
  color: #666;
  min-width: 36px;
  text-align: right;
}

.import-step {
  font-size: 12px;
  color: #888;
}

.import-error {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding: 6px 10px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  font-size: 13px;
  color: #ff4d4f;
}

.dismiss-btn {
  padding: 2px 8px;
  background: transparent;
  border: 1px solid #ffccc7;
  border-radius: 3px;
  font-size: 12px;
  color: #ff4d4f;
  cursor: pointer;
}

.dismiss-btn:hover {
  background: #fff2f0;
}
</style>
