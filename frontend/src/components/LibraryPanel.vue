<template>
  <div
    class="library-panel"
    :class="{ 'library-panel--drag-over': dragActive }"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
  >
    <!-- Drag overlay -->
    <Transition name="drag-fade">
      <div v-if="dragActive" class="drag-overlay">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <span>松开以导入 PDF</span>
      </div>
    </Transition>
    <!-- Sticky header: search + filters + upload -->
    <div class="library-header">
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
    </div>

    <!-- Scrollable body -->
    <div class="library-body">
      <!-- Trash view -->
      <TrashPanel
        v-if="viewMode === 'trash'"
        :papers="trashedPapers"
        :loading="trashedLoading"
        @restore="handleRestore"
        @permanent-delete="handlePermanentDelete"
        @back="viewMode = 'library'"
      />

      <!-- Library view -->
      <template v-else>
        <!-- Loading -->
        <div v-if="loading" class="library-empty">正在加载...</div>

        <!-- Error -->
        <div v-else-if="error" class="library-error">{{ error }}</div>

        <!-- Importing placeholder -->
        <div v-else-if="papers.length === 0 && importing && importQueue.length === 0" class="library-importing-state">
          <div class="importing-spinner"></div>
          <p class="importing-text">正在导入文献，请稍候...</p>
        </div>

        <!-- Batch import queue (empty library) -->
        <ImportQueueList
          v-else-if="papers.length === 0 && importQueue.length > 0"
          :items="importQueue"
          :is-empty-library="true"
          @retry="libraryStore.retryQueueItem($event)"
          @remove="libraryStore.removeQueueItem($event)"
        />

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
            @remove="handleRemove"
            @retry="handleRetry($event)"
            @preview="handlePreview"
          />

          <div class="library-summary">
            共 {{ papers.length }} 篇论文，已选 {{ selectedIds.length }} 篇
          </div>
        </div>
      </template>
    </div>

    <!-- Fixed footer: import status (always visible) -->
    <div v-if="hasImportStatus" class="library-footer">
      <!-- Import queue (non-empty library) -->
      <ImportQueueList
        v-if="importQueue.length > 0 && papers.length > 0"
        :items="importQueue"
        :is-empty-library="false"
        @retry="libraryStore.retryQueueItem($event)"
        @remove="libraryStore.removeQueueItem($event)"
      />

      <!-- Single file import progress -->
      <div v-else-if="importing && papers.length > 0" class="import-progress">
        <div class="import-info">
          <span class="import-filename">{{ importFileName || '正在导入...' }}</span>
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

    <!-- Bottom action bar: recycle bin + batch delete -->
    <div v-if="viewMode === 'library'" class="library-action-footer">
      <button
        type="button"
        class="library-recycle-btn"
        title="回收站"
        @click="switchToTrash()"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="3" width="20" height="5" rx="1" />
          <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
          <path d="M10 12h4" />
        </svg>
        <span>回收站</span>
      </button>
      <button
        v-if="selectedIds.length > 0"
        type="button"
        class="library-batch-delete-btn"
        title="删除选中论文"
        @click="handleBatchDelete"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          <line x1="10" y1="11" x2="10" y2="17" />
          <line x1="14" y1="11" x2="14" y2="17" />
        </svg>
        <span>删除 ({{ selectedIds.length }})</span>
      </button>
    </div>

    <!-- Delete confirmation dialog -->
    <DeleteConfirmDialog
      :visible="confirmDelete.visible"
      :title="confirmDelete.title"
      :count="confirmDelete.batchIds.length || 1"
      :skip-confirm="skipDeleteConfirm"
      @confirm="confirmDeleteAction"
      @cancel="confirmDelete.visible = false"
      @update:skip-confirm="skipDeleteConfirm = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import type { PaperItem } from '../types/paper'
import { useLibraryStore } from '../stores/library'
import { useUiStore } from '../stores/ui'
import { useLibrarySearch } from '../composables/use-library-search'
import { useDropZone } from '../composables/use-drop-zone'
import LibraryPaperCard from './LibraryPaperCard.vue'
import TrashPanel from './TrashPanel.vue'
import ImportQueueList from './ImportQueueList.vue'
import DeleteConfirmDialog from './DeleteConfirmDialog.vue'
import { storeToRefs } from 'pinia'

const libraryStore = useLibraryStore()
const uiStore = useUiStore()
const { importing, importFileName, importPercent, importStep, importError, importQueue } = storeToRefs(libraryStore)
const { trashedPapers } = storeToRefs(libraryStore)

const viewMode = ref<'library' | 'trash'>('library')
const trashedLoading = ref(false)

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

// 拖拽上传
const { dragActive, onDragEnter, onDragLeave, onDrop } = useDropZone((files) => {
  libraryStore.importFiles(files)
})

const showSortMenu = ref(false)

// 删除确认状态
const skipDeleteConfirm = ref(false)
const confirmDelete = reactive({ visible: false, paperId: '', title: '', batchIds: [] as string[] })

const search = useLibrarySearch(() => props.papers)

const hasImportStatus = computed(() =>
  (importQueue.value.length > 0 && props.papers.length > 0) ||
  (importing.value && props.papers.length > 0) ||
  !!importError.value,
)

const filteredPapers = computed(() => search.results.value)

onMounted(() => {
  if (libraryStore.importQueue.length > 0 && !libraryStore.importing) {
    libraryStore.resumeImports()
  }
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

function handlePreview(paperId: string) {
  uiStore.openReader(paperId)
}

function handleRetry(paperId: string) {
  emit('retry', paperId)
}

function handleRemove(paperId: string) {
  // 单篇删除：只删除这一篇，不涉及选中项
  if (skipDeleteConfirm.value) {
    emit('remove', paperId)
    return
  }

  const paper = props.papers.find((p) => p.paper_id === paperId)
  confirmDelete.paperId = paperId
  confirmDelete.title = paper?.title || paperId
  confirmDelete.batchIds = []
  confirmDelete.visible = true
}

function confirmDeleteAction() {
  if (confirmDelete.batchIds.length > 1) {
    for (const id of confirmDelete.batchIds) {
      emit('remove', id)
    }
  } else if (confirmDelete.batchIds.length === 1) {
    emit('remove', confirmDelete.batchIds[0])
  } else {
    emit('remove', confirmDelete.paperId)
  }
  confirmDelete.visible = false
}

function handleBatchDelete() {
  if (props.selectedIds.length === 0) return

  if (skipDeleteConfirm.value) {
    for (const id of props.selectedIds) {
      emit('remove', id)
    }
    return
  }

  confirmDelete.paperId = ''
  confirmDelete.title = `${props.selectedIds.length} 篇论文`
  confirmDelete.batchIds = [...props.selectedIds]
  confirmDelete.visible = true
}

async function switchToTrash() {
  viewMode.value = 'trash'
  trashedLoading.value = true
  try {
    await libraryStore.loadTrashedPapers()
  } finally {
    trashedLoading.value = false
  }
}

async function handleRestore(paperId: string) {
  try {
    await libraryStore.restorePaperFromTrash(paperId)
  } catch {
    // store 已设置 error
  }
}

async function handlePermanentDelete(paperId: string) {
  try {
    await libraryStore.permanentDeleteFromTrash(paperId)
  } catch {
    // store 已设置 error
  }
}
</script>

<style scoped>
.library-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  position: relative;
}

.library-panel--drag-over {
  outline: 2px dashed var(--color-accent);
  outline-offset: -2px;
}

/* ─── Drag overlay ─── */
.drag-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  background: color-mix(in srgb, var(--color-surface-card) 90%, transparent);
  backdrop-filter: blur(4px);
  border-radius: inherit;
  font-size: var(--font-size-sm);
  color: var(--color-accent);
  font-weight: 500;
  pointer-events: none;
}

.drag-fade-enter-active,
.drag-fade-leave-active {
  transition: opacity 0.15s ease;
}

.drag-fade-enter-from,
.drag-fade-leave-to {
  opacity: 0;
}

/* ─── Sticky header ─── */
.library-header {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  background: var(--color-surface-card);
  z-index: 5;
}

/* ─── Scrollable body ─── */
.library-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* ─── Fixed footer for import status ─── */
.library-footer {
  flex-shrink: 0;
  border-top: 1px solid var(--color-border-subtle);
  background: var(--color-surface-card);
  z-index: 5;
}

/* ─── Bottom action bar ─── */
.library-action-footer {
  flex-shrink: 0;
  border-top: 1px solid var(--color-border-subtle);
  background: var(--color-surface-card);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
}

.library-recycle-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.library-recycle-btn:hover {
  color: var(--color-text-secondary);
  background: var(--color-surface-muted);
}

.library-batch-delete-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-error);
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.library-batch-delete-btn:hover {
  background: color-mix(in srgb, var(--color-error) 8%, transparent);
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

/* ─── Importing state (single-file spinner) ─── */
.library-importing-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-4);
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

/* ─── Import progress (single-file) ─── */
.import-progress {
  padding: var(--space-3);
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
