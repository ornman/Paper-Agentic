<template>
  <div class="import-queue" :class="{ 'import-queue--empty-library': isEmptyLibrary }">
    <div
      v-for="(item, idx) in items"
      :key="item.fileName"
      class="import-queue-item"
      :class="'import-queue-item--' + item.status"
    >
      <span class="import-queue-icon">
        <svg v-if="item.status === 'completed'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        <span v-else-if="item.status === 'importing'" class="import-queue-spinner"></span>
        <span v-else class="import-queue-dot"></span>
      </span>
      <div class="import-queue-body">
        <div class="import-queue-filename">{{ item.fileName }}</div>
        <div v-if="item.status === 'importing'" class="import-queue-bar-track">
          <div class="import-queue-bar-fill" :style="{ width: item.percent + '%' }"></div>
        </div>
        <div class="import-queue-step">{{ item.step }}</div>
      </div>
      <div class="import-queue-actions">
        <span v-if="item.status === 'importing'" class="import-queue-percent">{{ item.percent }}%</span>
        <button v-if="item.status === 'failed' && item.file" type="button" class="import-queue-retry" title="重试" @click="emit('retry', idx)">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
        </button>
        <button v-if="item.status === 'failed'" type="button" class="import-queue-remove" title="移除" @click="emit('remove', idx)">×</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ImportQueueItem } from '../types/paper'

defineProps<{
  items: ImportQueueItem[]
  isEmptyLibrary: boolean
}>()

const emit = defineEmits<{
  (e: 'retry', idx: number): void
  (e: 'remove', idx: number): void
}>()
</script>

<style scoped>
/* ─── Import queue (list) ─── */
.import-queue {
  display: flex;
  flex-direction: column;
  gap: 1px;
  max-height: 220px;
  overflow-y: auto;
}

.import-queue--empty-library {
  flex: 1;
  max-height: none;
  justify-content: center;
  overflow-y: visible;
}

.import-queue-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  transition: background 0.15s ease;
}

.import-queue-item--completed {
  opacity: 0.65;
}

.import-queue-item--failed {
  background: color-mix(in srgb, var(--color-error, #c53030) 5%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-error, #c53030) 20%, transparent);
  border-radius: var(--radius-sm);
}

.import-queue-item--failed .import-queue-filename {
  color: var(--color-error, #c53030);
}

.import-queue-item--failed .import-queue-step {
  color: var(--color-error, #c53030);
  opacity: 0.8;
}

.import-queue-icon {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.import-queue-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-border-subtle);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.import-queue-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-border-subtle);
}

.import-queue-body {
  flex: 1;
  min-width: 0;
}

.import-queue-filename {
  font-size: 12px;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-queue-item--completed .import-queue-filename {
  text-decoration: line-through;
  text-decoration-color: var(--color-text-muted);
}

.import-queue-bar-track {
  height: 3px;
  margin-top: 4px;
  background: var(--color-surface-muted);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.import-queue-bar-fill {
  height: 100%;
  background: var(--color-accent);
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

.import-queue-step {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.import-queue-percent {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--color-accent);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  margin-top: 1px;
}

.import-queue-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.import-queue-retry {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.import-queue-retry:hover {
  color: var(--color-accent);
  background: var(--color-surface-muted);
}

.import-queue-remove {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.import-queue-remove:hover {
  color: var(--color-text-primary);
  background: var(--color-surface-muted);
}
</style>
