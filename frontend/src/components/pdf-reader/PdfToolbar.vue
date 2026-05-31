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

      <span class="reader-divider" />

      <button
        class="reader-btn"
        :class="{ 'reader-btn-active': searchOpen }"
        aria-label="搜索"
        @click="emit('open-search')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </button>

      <span class="reader-divider" />

      <!-- View mode dropdown -->
      <div class="view-mode-wrapper" ref="viewModeWrapperRef">
        <button
          class="reader-btn"
          :class="{ 'reader-btn-active': viewMode !== 'single' }"
          aria-label="视图模式"
          title="视图模式"
          @click="viewModeMenuOpen = !viewModeMenuOpen"
        >
          <!-- Icon matches current mode -->
          <svg v-if="viewMode === 'single'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="6" y="3" width="12" height="18" rx="1"/>
          </svg>
          <svg v-else-if="viewMode === 'double'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="8" height="18" rx="1"/>
            <rect x="14" y="3" width="8" height="18" rx="1"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="6" y="1" width="12" height="6" rx="1"/>
            <rect x="6" y="9" width="12" height="6" rx="1"/>
            <rect x="6" y="17" width="12" height="6" rx="1"/>
          </svg>
          <svg class="view-mode-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>

        <div v-if="viewModeMenuOpen" class="view-mode-dropdown">
          <button
            class="view-mode-option"
            :class="{ 'view-mode-option-active': viewMode === 'single' }"
            @click="selectViewMode('single')"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="6" y="3" width="12" height="18" rx="1"/>
            </svg>
            <span>单页</span>
          </button>
          <button
            class="view-mode-option"
            :class="{ 'view-mode-option-active': viewMode === 'double' }"
            @click="selectViewMode('double')"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="3" width="8" height="18" rx="1"/>
              <rect x="14" y="3" width="8" height="18" rx="1"/>
            </svg>
            <span>双页</span>
          </button>
          <button
            class="view-mode-option"
            :class="{ 'view-mode-option-active': viewMode === 'continuous' }"
            @click="selectViewMode('continuous')"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="6" y="1" width="12" height="6" rx="1"/>
              <rect x="6" y="9" width="12" height="6" rx="1"/>
              <rect x="6" y="17" width="12" height="6" rx="1"/>
            </svg>
            <span>连续滚动</span>
          </button>
        </div>
      </div>

      <PdfSearchBar
        v-if="searchOpen"
        :query="searchQuery"
        :match-count="searchMatchCount"
        :current-match-index="searchCurrentIndex"
        @search="(q: string) => emit('search', q)"
        @next="emit('search-next')"
        @prev="emit('search-prev')"
        @close="emit('search-close')"
      />
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import PdfSearchBar from './PdfSearchBar.vue'
import type { ViewMode } from '../../composables/use-pdf-renderer'

const props = defineProps<{
  title: string
  currentPage: number
  totalPages: number
  scale: number
  outlineOpen: boolean
  showOutlineButton: boolean
  searchOpen: boolean
  searchQuery: string
  searchMatchCount: number
  searchCurrentIndex: number
  viewMode: ViewMode
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'prev'): void
  (e: 'next'): void
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'go-to-page', page: number): void
  (e: 'toggle-outline'): void
  (e: 'open-search'): void
  (e: 'search', query: string): void
  (e: 'search-next'): void
  (e: 'search-prev'): void
  (e: 'search-close'): void
  (e: 'set-view-mode', mode: ViewMode): void
}>()

const pageInputRef = ref<HTMLInputElement | null>(null)
const viewModeMenuOpen = ref(false)
const viewModeWrapperRef = ref<HTMLElement | null>(null)

function selectViewMode(mode: ViewMode) {
  emit('set-view-mode', mode)
  viewModeMenuOpen.value = false
}

function handleClickOutside(e: MouseEvent) {
  if (viewModeWrapperRef.value && !viewModeWrapperRef.value.contains(e.target as Node)) {
    viewModeMenuOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', handleClickOutside))

function handlePageInput() {
  const raw = pageInputRef.value
  if (!raw) return
  const val = parseInt(raw.value, 10)
  if (isNaN(val)) { raw.value = String(props.currentPage); return }
  const clamped = Math.max(1, Math.min(props.totalPages, val))
  raw.value = String(clamped)
  if (clamped !== props.currentPage) {
    emit('go-to-page', clamped)
  }
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
  min-width: 0;
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

/* View mode dropdown */
.view-mode-wrapper {
  position: relative;
}

.view-mode-chevron {
  margin-left: 1px;
  opacity: 0.6;
}

.view-mode-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: var(--color-surface-primary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  padding: var(--space-1);
  z-index: 100;
  min-width: 120px;
}

.view-mode-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
}

.view-mode-option:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.view-mode-option-active {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}
</style>
