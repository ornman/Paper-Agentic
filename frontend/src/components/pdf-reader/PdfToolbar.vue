<template>
  <div class="reader-toolbar">
    <div class="reader-title" :title="title">{{ title }}</div>

    <template v-if="showOutlineButton">
      <button
        class="reader-btn"
        :class="{ 'reader-btn-active': outlineOpen }"
        aria-label="目录"
        @click="emit('toggle-outline')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="8" y1="6" x2="21" y2="6"/>
          <line x1="8" y1="12" x2="21" y2="12"/>
          <line x1="8" y1="18" x2="21" y2="18"/>
          <line x1="3" y1="6" x2="3.01" y2="6"/>
          <line x1="3" y1="12" x2="3.01" y2="12"/>
          <line x1="3" y1="18" x2="3.01" y2="18"/>
        </svg>
      </button>
    </template>

    <div class="reader-controls">
      <button
        class="reader-btn"
        :disabled="currentPage <= 1"
        aria-label="上一页"
        @click="emit('prev')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>

      <span class="reader-page-info">
        <input
          ref="pageInputRef"
          class="reader-page-input"
          type="number"
          :value="currentPage"
          :min="1"
          :max="totalPages"
          @keydown.enter="handlePageInput"
          @blur="handlePageInput"
        />
        <span class="reader-page-sep">/</span>
        <span>{{ totalPages }}</span>
      </span>

      <button
        class="reader-btn"
        :disabled="currentPage >= totalPages"
        aria-label="下一页"
        @click="emit('next')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      </button>

      <span class="reader-divider" />

      <button
        class="reader-btn"
        :disabled="scale <= 0.5"
        aria-label="缩小"
        @click="emit('zoom-out')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
      </button>

      <span class="reader-scale-label">{{ Math.round(scale * 100) }}%</span>

      <button
        class="reader-btn"
        :disabled="scale >= 3"
        aria-label="放大"
        @click="emit('zoom-in')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      </button>
    </div>

    <button
      class="reader-close-btn"
      type="button"
      aria-label="关闭阅读面板"
      @click="emit('close')"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  title: string
  currentPage: number
  totalPages: number
  scale: number
  outlineOpen: boolean
  showOutlineButton: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'prev'): void
  (e: 'next'): void
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'go-to-page', page: number): void
  (e: 'toggle-outline'): void
}>()

const pageInputRef = ref<HTMLInputElement | null>(null)

function handlePageInput() {
  const raw = pageInputRef.value
  if (!raw) return
  const val = parseInt(raw.value, 10)
  if (isNaN(val)) { raw.value = String(props.currentPage); return }
  const clamped = Math.max(1, Math.min(props.totalPages, val))
  raw.value = String(clamped)
  emit('go-to-page', clamped)
}
</script>

<style scoped>
.reader-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.reader-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 80px;
  max-width: 300px;
}

.reader-controls {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  justify-content: center;
}

.reader-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  transition: background 0.15s, color 0.15s;
}

.reader-btn:hover:not(:disabled) {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.reader-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.reader-btn-active {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

.reader-page-info {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.reader-page-input {
  width: 36px;
  text-align: center;
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-primary);
  background: var(--color-surface-muted);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 2px 0;
  outline: none;
  transition: border-color 0.15s;
}

.reader-page-input:focus {
  border-color: var(--color-accent);
}

.reader-page-input::-webkit-inner-spin-button,
.reader-page-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.reader-page-input[type='number'] {
  -moz-appearance: textfield;
}

.reader-page-sep {
  color: var(--color-text-muted);
}

.reader-divider {
  width: 1px;
  height: 16px;
  background: var(--color-border-subtle);
  margin: 0 var(--space-1);
}

.reader-scale-label {
  font-size: 11px;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  min-width: 36px;
  text-align: center;
}

.reader-close-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.reader-close-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}
</style>
