<template>
  <div class="library-panel">
    <!-- Search (always visible) -->
    <div class="library-search">
      <svg class="library-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        v-model="searchText"
        type="text"
        class="library-search-input"
        placeholder="搜索论文..."
        aria-label="搜索文献库"
      />
      <div class="sort-wrapper">
        <button class="sort-toggle" type="button" @click="showSortMenu = !showSortMenu" title="排序">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 4h12M4 8h8M6 12h4"/></svg>
        </button>
        <div v-if="showSortMenu" class="sort-menu" @mouseleave="showSortMenu = false">
          <button :class="{ active: sortBy === 'time' }" @click="sortBy = 'time'; showSortMenu = false">按导入时间</button>
          <button :class="{ active: sortBy === 'title' }" @click="sortBy = 'title'; showSortMenu = false">按标题</button>
          <button :class="{ active: sortBy === 'pages' }" @click="sortBy = 'pages'; showSortMenu = false">按页数</button>
        </div>
      </div>
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
      上传论文
    </button>

    <!-- Loading -->
    <div v-if="loading" class="library-empty">加载中...</div>

    <!-- Error -->
    <div v-else-if="error" class="library-error">{{ error }}</div>

    <!-- Empty state -->
    <div v-else-if="papers.length === 0" class="library-empty-state">
      <p class="library-empty-text">还没有导入论文</p>
      <button class="library-upload-btn library-upload-btn--prominent" type="button" @click="emit('upload')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        上传论文
      </button>
    </div>

    <!-- No search results -->
    <div v-else-if="filteredPapers.length === 0 && searchText" class="library-empty">
      未找到匹配的论文
    </div>

    <!-- Paper list -->
    <div v-else class="library-list">
      <!-- Select all header -->
      <label v-if="sortedPapers.length > 0" class="library-select-all">
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
      </label>

      <label
        v-for="paper in sortedPapers"
        :key="paper.paper_id"
        class="library-item"
        :class="{ 'library-item--selected': selectedIds.includes(paper.paper_id) }"
      >
        <input
          type="checkbox"
          class="library-item-checkbox"
          :value="paper.paper_id"
          :checked="selectedIds.includes(paper.paper_id)"
          @change="emit('toggle', paper.paper_id)"
        />
        <div class="library-item-body">
          <span class="library-item-title">{{ paper.title }}</span>
          <span class="library-item-meta">
            {{ truncateAuthors(paper.authors) }}
            &middot; {{ paper.total_pages }} 页
            &middot; {{ paper.chunk_count }} 块
            &middot; {{ relativeTime(paper.import_time) }}
          </span>
        </div>
        <button
          class="library-item-remove"
          type="button"
          aria-label="移除论文"
          @click.prevent.stop="emit('remove', paper.paper_id)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </label>

      <!-- Summary footer -->
      <div class="library-summary">
        共 {{ papers.length }} 篇论文，已选 {{ selectedIds.length }} 篇
      </div>
    </div>

    <!-- Import progress -->
    <div v-if="importing" class="import-progress">
      <div class="import-info">
        <span class="import-filename">{{ importFileName || '正在导入...' }}</span>
        <span class="import-percent">{{ importPercent }}%</span>
      </div>
      <div class="import-bar-track">
        <div class="import-bar-fill" :style="{ width: importPercent + '%' }"></div>
      </div>
      <div v-if="importStep" class="import-step">{{ importStep }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PaperItem } from '../services/library-api'
import { useLibraryStore } from '../stores/library'

const libraryStore = useLibraryStore()

const { importing, importFileName, importPercent, importStep } = libraryStore

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
}>()

const searchText = ref('')
const sortBy = ref<'time' | 'title' | 'pages'>('time')
const showSortMenu = ref(false)

const filteredPapers = computed(() => {
  if (!searchText.value.trim()) return props.papers
  const q = searchText.value.toLowerCase()
  return props.papers.filter(
    (paper) =>
      paper.title.toLowerCase().includes(q) ||
      paper.authors.toLowerCase().includes(q),
  )
})

const sortedPapers = computed(() => {
  const list = [...filteredPapers.value]
  if (sortBy.value === 'title') {
    list.sort((a, b) => a.title.localeCompare(b.title))
  } else if (sortBy.value === 'pages') {
    list.sort((a, b) => (b.total_pages ?? 0) - (a.total_pages ?? 0))
  } else {
    list.sort((a, b) => new Date(b.import_time).getTime() - new Date(a.import_time).getTime())
  }
  return list
})

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

function truncateAuthors(authors: string, maxLen = 30): string {
  if (!authors) return '未知作者'
  if (authors.length <= maxLen) return authors
  return authors.slice(0, maxLen) + '...'
}

function relativeTime(iso: string): string {
  if (!iso) return ''
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diffMs = now - then
  if (diffMs < 0) return '刚刚'

  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`

  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`

  const months = Math.floor(days / 30)
  if (months < 12) return `${months} 个月前`

  const years = Math.floor(months / 12)
  return `${years} 年前`
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
  padding: var(--space-2) 36px var(--space-2) calc(var(--space-3) + 18px);
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

/* ─── Paper list ─── */
.library-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
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

.library-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.25s ease, box-shadow 0.25s ease;
}

.library-item:hover {
  background: var(--color-surface-muted);
}

.library-item--selected {
  background: var(--color-accent-soft);
  box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--color-accent) 25%, transparent);
}

.library-item--selected:hover {
  background: var(--color-accent-soft);
}

.library-item-checkbox {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  accent-color: var(--color-accent);
  cursor: pointer;
}

.library-item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.library-item-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.library-item-meta {
  font-size: 12px;
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.library-item-remove {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--color-text-muted);
  opacity: 0;
  transition: opacity var(--duration-fast) ease, color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.library-item:hover .library-item-remove {
  opacity: 1;
}

.library-item-remove:hover {
  color: var(--color-error);
  background: var(--color-surface-muted);
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
  width: 32px;
  height: 32px;
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
</style>
