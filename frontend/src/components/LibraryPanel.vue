<template>
  <div class="library-panel">
    <!-- Search bar -->
    <div class="library-search">
      <svg class="library-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        v-model="search.query.value"
        type="text"
        class="library-search-input"
        placeholder="搜索标题、作者、关键词..."
        aria-label="搜索文献库"
      />
      <div class="search-actions">
        <button v-if="search.hasQuery.value" class="search-clear" type="button" @click="search.resetFilters()" title="清除搜索">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
        <div class="sort-wrapper">
          <button class="sort-toggle" type="button" @click="showSortMenu = !showSortMenu" title="排序">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 4h12M4 8h8M6 12h4"/></svg>
          </button>
          <div v-if="showSortMenu" class="sort-menu" @mouseleave="showSortMenu = false">
            <button :class="{ active: search.sortBy.value === 'relevance' }" @click="search.sortBy.value = 'relevance'; showSortMenu = false">相关度</button>
            <button :class="{ active: search.sortBy.value === 'time' }" @click="search.sortBy.value = 'time'; showSortMenu = false">导入时间</button>
            <button :class="{ active: search.sortBy.value === 'year' }" @click="search.sortBy.value = 'year'; showSortMenu = false">发表年份</button>
            <button :class="{ active: search.sortBy.value === 'title' }" @click="search.sortBy.value = 'title'; showSortMenu = false">标题</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Filter row -->
    <div v-if="papers.length > 0" class="library-filters">
      <select v-model="search.yearFilter.value" class="filter-select" :class="{ 'filter-active': search.yearFilter.value }">
        <option value="">年份</option>
        <option v-for="y in search.yearOptions.value" :key="y" :value="y">{{ y }}</option>
      </select>
      <select v-model="search.authorFilter.value" class="filter-select" :class="{ 'filter-active': search.authorFilter.value }">
        <option value="">作者</option>
        <option v-for="a in search.authorOptions.value" :key="a" :value="a">{{ a }}</option>
      </select>
    </div>

    <!-- Upload button -->
    <button
      v-if="filteredPapers.length > 0 || papers.length > 0"
      class="library-upload-btn"
      type="button"
      @click="emit('upload')"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      导入论文
    </button>

    <!-- Loading -->
    <div v-if="loading" class="library-empty">正在加载...</div>

    <!-- Error -->
    <div v-else-if="error" class="library-error">{{ error }}</div>

    <!-- Importing placeholder (replaces empty state during import) -->
    <div v-else-if="papers.length === 0 && importing" class="library-importing-state">
      <div class="importing-spinner"></div>
      <p class="importing-text">
        <template v-if="importBatchTotal > 1">正在导入 ({{ importBatchCurrent }}/{{ importBatchTotal }})...</template>
        <template v-else>正在导入文献，请稍候...</template>
      </p>
    </div>

    <!-- Empty state -->
    <div v-else-if="papers.length === 0" class="library-empty-state">
      <p class="library-empty-text">开始导入你的第一篇论文</p>
      <p class="library-empty-hint">支持 PDF 格式，拖拽或点击上传</p>
      <button class="library-upload-btn library-upload-btn--prominent" type="button" @click="emit('upload')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        导入论文
      </button>
    </div>

    <!-- No search results -->
    <div v-else-if="filteredPapers.length === 0 && (search.hasQuery.value || search.yearFilter.value || search.authorFilter.value)" class="library-empty">
      未找到匹配的论文，试试调整搜索关键词
    </div>

    <!-- Paper list -->
    <div v-else class="library-list">
      <!-- Select all header -->
      <label v-if="filteredPapers.length > 0" class="library-select-all">
        <input
          type="checkbox"
          class="library-item-checkbox"
          :checked="allFilteredSelected"
          :indeterminate.prop="someFilteredSelected && !allFilteredSelected"
          @change="handleSelectAll"
        />
        <span class="library-select-all-label">
          {{ allFilteredSelected ? '取消全选' : '全选' }}
        </span>
        <span v-if="search.hasQuery.value || search.yearFilter.value || search.authorFilter.value" class="library-result-count">
          {{ search.totalResults.value }} / {{ papers.length }}
        </span>
      </label>

      <LibraryPaperCard
        v-for="paper in filteredPapers"
        :key="paper.paper_id"
        :paper="paper"
        :selected="selectedIds.includes(paper.paper_id)"
        :highlight-fn="search.highlightText"
        @toggle="emit('toggle', $event)"
        @remove="emit('remove', $event)"
        @retry="handleRetry($event)"
        @preview="handlePreview"
      />

      <!-- Summary footer -->
      <div class="library-summary">
        共 {{ papers.length }} 篇论文，已选 {{ selectedIds.length }} 篇
      </div>
    </div>

    <!-- Import progress -->
    <div v-if="importing" class="import-progress">
      <div class="import-info">
        <span class="import-filename">
          <template v-if="importBatchTotal > 1" class="import-batch-badge">({{ importBatchCurrent }}/{{ importBatchTotal }})</template>
          {{ importFileName || '正在导入...' }}
        </span>
        <span class="import-percent">{{ importPercent }}%</span>
      </div>
      <div class="import-bar-track">
        <div class="import-bar-fill" :style="{ width: importPercent + '%' }"></div>
      </div>
      <div v-if="importStep" class="import-step">{{ importStep }}</div>
    </div>

    <!-- Import error -->
    <div v-if="importError" class="import-error">
      <span class="import-error-icon">!</span>
      <span class="import-error-text">{{ importError }}</span>
      <button class="import-error-close" type="button" @click="libraryStore.clearImportError()">×</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PaperItem } from '../services/library-api'
import { useLibraryStore } from '../stores/library'
import { useUiStore } from '../stores/ui'
import { useLibrarySearch } from '../composables/use-library-search'
import LibraryPaperCard from './LibraryPaperCard.vue'
import { storeToRefs } from 'pinia'

const libraryStore = useLibraryStore()
const uiStore = useUiStore()
const { importing, importFileName, importPercent, importStep, importError, importBatchTotal, importBatchCurrent } = storeToRefs(libraryStore)

const props = defineProps<{
  papers: PaperItem[]
  loading: boolean
  error: string | null
  selectedIds: string[]
}>()

const emit = defineEmits<{
  (e: 'toggle', id: string): void
  (e: 'upload'): void
  (e: 'remove', id: string): void
  (e: 'select-all', ids: string[]): void
  (e: 'retry', paperId: string): void
}>()

const showSortMenu = ref(false)

const search = useLibrarySearch(() => props.papers)

const filteredPapers = computed(() => search.results.value)

const filteredIds = computed(() => filteredPapers.value.map((p) => p.paper_id))

const allFilteredSelected = computed(
  () =>
    filteredIds.value.length > 0 &&
    filteredIds.value.every((id) => props.selectedIds.includes(id)),
)

const someFilteredSelected = computed(() =>
  filteredIds.value.some((id) => props.selectedIds.includes(id)),
)

function handleSelectAll() {
  if (allFilteredSelected.value) {
    emit('select-all', [])
  } else {
    emit('select-all', filteredIds.value)
  }
}

function handlePreview(paperId: string) {
  uiStore.openReader(paperId)
}

function handleRetry(paperId: string) {
  emit('retry', paperId)
}
</script>

<style scoped>
.library-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 0;
}

/* ─── Search ─── */
.library-search {
  position: relative;
  display: flex;
  align-items: center;
}

.library-search-icon {
  position: absolute;
  left: var(--space-3);
  color: var(--color-text-muted);
  pointer-events: none;
}

.library-search-input {
  width: 100%;
  padding: var(--space-2) 72px var(--space-2) calc(var(--space-3) + 18px);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  background: var(--color-surface-base);
  outline: none;
  transition: border-color var(--duration-fast) ease;
}

.library-search-input:focus {
  border-color: var(--color-accent);
}

.library-search-input::placeholder {
  color: var(--color-text-muted);
}

.search-actions {
  position: absolute;
  right: 4px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.search-clear {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.search-clear:hover {
  color: var(--color-text-primary);
  background: var(--color-surface-muted);
}

/* ─── Filters ─── */
.library-filters {
  display: flex;
  gap: var(--space-2);
}

.filter-select {
  flex: 1;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-surface-base);
  outline: none;
  cursor: pointer;
  transition: border-color var(--duration-fast) ease;
}

.filter-select:focus {
  border-color: var(--color-accent);
}

.filter-active {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

/* ─── Upload button ─── */
.library-upload-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  background: transparent;
  transition: background var(--duration-fast) ease, border-color var(--duration-fast) ease;
}

.library-upload-btn:hover {
  background: var(--color-surface-muted);
  border-color: var(--color-border-strong);
}

.library-upload-btn--prominent {
  padding: var(--space-3) var(--space-5);
  background: var(--color-accent);
  color: var(--color-surface-card);
  border-color: var(--color-accent);
}

.library-upload-btn--prominent:hover {
  opacity: 0.9;
  background: var(--color-accent);
}

/* ─── States ─── */
.library-empty {
  text-align: center;
  padding: var(--space-6) var(--space-4);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.library-error {
  text-align: center;
  padding: var(--space-4);
  color: var(--color-error);
  font-size: var(--font-size-sm);
}

.library-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-6) var(--space-4);
}

.library-empty-text {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.library-empty-hint {
  font-size: 11px;
  color: var(--color-text-muted);
  opacity: 0.7;
  margin: 0;
}

/* ─── Paper list ─── */
.library-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  position: relative;
}

/* ─── Select all ─── */
.library-select-all {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border-subtle);
  margin-bottom: var(--space-1);
  cursor: pointer;
}

.library-select-all-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  user-select: none;
}

.library-result-count {
  font-size: 11px;
  color: var(--color-accent);
  margin-left: auto;
}

.library-item-checkbox {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  accent-color: var(--color-accent);
  cursor: pointer;
}

/* ─── Summary ─── */
.library-summary {
  padding: var(--space-2) var(--space-3);
  font-size: 12px;
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border-subtle);
  text-align: center;
  user-select: none;
}

/* ─── Sort ─── */
.sort-wrapper {
  position: relative;
}

.sort-toggle {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.sort-toggle:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.sort-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 120px;
  padding: var(--space-1);
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  z-index: 10;
}

.sort-menu button {
  display: block;
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.sort-menu button:hover {
  background: var(--color-surface-muted);
}

.sort-menu button.active {
  color: var(--color-accent);
  font-weight: 600;
}

/* ─── Importing state (replaces empty state) ─── */
.library-importing-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-4);
}

.importing-spinner {
  width: 24px;
  height: 24px;
  border: 2.5px solid var(--color-border-subtle);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.importing-text {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

/* ─── Import progress ─── */
.import-progress {
  padding: var(--space-3);
  border-top: 1px solid var(--color-border-subtle);
}

.import-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.import-filename {
  font-size: 12px;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 70%;
}

.import-percent {
  font-size: 12px;
  color: var(--color-accent);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.import-bar-track {
  height: 4px;
  background: var(--color-surface-muted);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.import-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-accent), color-mix(in srgb, var(--color-accent) 70%, #fff));
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

.import-step {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: var(--space-1);
}

.import-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  margin-top: var(--space-2);
  background: color-mix(in srgb, var(--color-error, #c53030) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-error, #c53030) 25%, transparent);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--color-error, #c53030);
}

.import-error-icon {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-error, #c53030);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}

.import-error-text {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}

.import-error-close {
  flex-shrink: 0;
  border: none;
  background: none;
  color: var(--color-error, #c53030);
  font-size: 16px;
  cursor: pointer;
  padding: 0 2px;
  opacity: 0.6;
}

.import-error-close:hover {
  opacity: 1;
}
</style>
