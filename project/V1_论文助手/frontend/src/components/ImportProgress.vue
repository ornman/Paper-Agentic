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
  padding: var(--claude-spacing-md) var(--claude-spacing-lg);
  background: var(--claude-primary-light);
  border: 1px solid #E8D5CC;
  border-radius: var(--claude-radius-md);
}

.import-header {
  display: flex;
  align-items: center;
  gap: var(--claude-spacing-sm);
  margin-bottom: var(--claude-spacing-sm);
  font-size: 14px;
  font-weight: 500;
  color: var(--claude-text-primary);
}

.import-filename {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-bar-wrapper {
  display: flex;
  align-items: center;
  gap: var(--claude-spacing-sm);
  margin-bottom: var(--claude-spacing-xs);
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--claude-border);
  border-radius: var(--claude-radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--claude-primary);
  border-radius: var(--claude-radius-full);
  transition: width 0.3s ease;
}

.progress-percent {
  font-size: 12px;
  color: var(--claude-text-secondary);
  min-width: 36px;
  text-align: right;
}

.import-step {
  font-size: 12px;
  color: var(--claude-text-muted);
}

.import-error {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--claude-spacing-sm);
  padding: var(--claude-spacing-xs) var(--claude-spacing-sm);
  background: #FFF5F3;
  border: 1px solid #F5C6C0;
  border-radius: var(--claude-radius-sm);
  font-size: 13px;
  color: var(--claude-error);
}

.dismiss-btn {
  padding: 2px 8px;
  background: transparent;
  border: 1px solid #F5C6C0;
  border-radius: 3px;
  font-size: 12px;
  color: var(--claude-error);
  cursor: pointer;
}

.dismiss-btn:hover {
  background: #FFF5F3;
}
</style>
