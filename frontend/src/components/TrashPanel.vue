<template>
  <div class="trash-panel">
    <!-- Header -->
    <div class="trash-header">
      <button type="button" class="trash-back-btn" @click="emit('back')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        <span>返回文献库</span>
      </button>
      <span class="trash-title">回收站</span>
    </div>

    <!-- Body -->
    <div class="trash-body">
      <!-- Loading -->
      <div v-if="loading" class="trash-empty">正在加载...</div>

      <!-- Empty -->
      <div v-else-if="papers.length === 0" class="trash-empty-state">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.5">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
        <p class="trash-empty-text">回收站是空的</p>
        <p class="trash-empty-hint">删除的论文会在这里保留，可随时恢复</p>
      </div>

      <!-- Paper list -->
      <div v-else class="trash-list">
        <div v-for="paper in papers" :key="paper.paper_id" class="trash-item">
          <div class="trash-item-info">
            <span class="trash-item-title">{{ paper.title }}</span>
            <span class="trash-item-meta">
              <span v-if="paper.authors">{{ paper.authors }}</span>
              <span v-if="paper.authors && paper.year"> · </span>
              <span v-if="paper.year">{{ paper.year }}</span>
            </span>
          </div>
          <div class="trash-item-actions">
            <button type="button" class="trash-action-btn trash-action-restore" @click="emit('restore', paper.paper_id)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
              恢复
            </button>
            <button type="button" class="trash-action-btn trash-action-delete" @click="handlePermanentDelete(paper)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              永久删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Permanent delete confirmation (reuses shared dialog) -->
    <DeleteConfirmDialog
      :visible="confirmVisible"
      :title="confirmTitle"
      :count="1"
      :skip-confirm="false"
      warning="此操作不可恢复"
      @confirm="doPermanentDelete"
      @cancel="confirmVisible = false"
      @update:skip-confirm="() => {}"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { PaperItem } from '../types/paper'
import DeleteConfirmDialog from './DeleteConfirmDialog.vue'

defineProps<{
  papers: PaperItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'restore', id: string): void
  (e: 'permanent-delete', id: string): void
  (e: 'back'): void
}>()

const confirmVisible = ref(false)
const confirmId = ref('')
const confirmTitle = ref('')

function handlePermanentDelete(paper: PaperItem) {
  confirmId.value = paper.paper_id
  confirmTitle.value = paper.title
  confirmVisible.value = true
}

function doPermanentDelete() {
  emit('permanent-delete', confirmId.value)
  confirmVisible.value = false
}
</script>

<style scoped>
.trash-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

/* ─── Header ─── */
.trash-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border-subtle);
}

.trash-back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.trash-back-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-surface-muted);
}

.trash-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

/* ─── Body ─── */
.trash-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}

.trash-empty {
  text-align: center;
  padding: var(--space-6) var(--space-4);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.trash-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6) var(--space-4);
}

.trash-empty-text {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.trash-empty-hint {
  font-size: 11px;
  color: var(--color-text-muted);
  opacity: 0.7;
  margin: 0;
}

/* ─── List ─── */
.trash-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trash-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  transition: background 0.15s ease;
}

.trash-item:hover {
  background: var(--color-surface-muted);
}

.trash-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trash-item-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trash-item-meta {
  font-size: 11px;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trash-item-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.trash-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease, border-color 0.15s ease;
}

.trash-action-restore {
  background: transparent;
  color: var(--color-text-muted);
}

.trash-action-restore:hover {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.trash-action-delete {
  background: transparent;
  color: var(--color-text-muted);
}

.trash-action-delete:hover {
  color: var(--color-error, #c53030);
  border-color: var(--color-error, #c53030);
}
</style>
