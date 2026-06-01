<template>
  <Teleport to="body">
    <Transition name="reader-backdrop">
      <div
        v-if="visible"
        class="reader-backdrop"
        @click="emit('close')"
      />
    </Transition>

    <Transition name="reader-panel">
      <div
        v-if="visible"
        class="reader-panel"
        role="dialog"
        aria-modal="true"
        aria-label="PDF 阅读面板"
        tabindex="-1"
        @keydown.escape="handleEscape"
      >
        <!-- Toolbar -->
        <PdfToolbar
          :title="paperTitle"
          :current-page="renderer.currentPage.value"
          :total-pages="renderer.totalPages.value"
          :scale="scale"
          :outline-open="outlineOpen"
          :show-outline-button="hasOutline"
          :search-open="search.isOpen.value"
          :search-query="search.query.value"
          :search-match-count="search.matchCount.value"
          :search-current-index="search.currentMatchIndex.value"
          :view-mode="viewMode"
          @close="emit('close')"
          @prev="goPrev"
          @next="goNext"
          @zoom-in="setScale(Math.min(3, scale + 0.25))"
          @zoom-out="setScale(Math.max(0.5, scale - 0.25))"
          @go-to-page="renderer.scrollToPage"
          @toggle-outline="outlineOpen = !outlineOpen"
          @open-search="search.openSearch()"
          @search="(q: string) => search.search(q)"
          @search-next="search.nextMatch()"
          @search-prev="search.prevMatch()"
          @search-close="search.closeSearch()"
          @set-view-mode="setViewMode"
        />

        <!-- PDF viewport -->
        <div class="reader-content">
          <PdfOutline
            :open="outlineOpen"
            :items="outlineItems"
            :current-page="renderer.currentPage.value"
            @close="outlineOpen = false"
            @navigate="(p: number) => renderer.scrollToPage(p)"
          />
          <div
            ref="scrollContainerRef"
            class="reader-body"
            :class="{
              'reader-body--single': viewMode === 'single',
              'reader-body--double': viewMode === 'double',
            }"
          >
            <div v-if="loading" class="reader-loading">
              <div class="reader-spinner" />
              <span>加载中…</span>
            </div>
            <div v-else-if="error" class="reader-error">
              <span>{{ error }}</span>
              <button class="reader-btn" @click="loadPdf">重试</button>
            </div>
            <div v-else-if="pdfDocProxy" class="reader-pages" :class="{ 'reader-pages--double': viewMode === 'double' }">
              <!-- 优化 4: 只渲染视口附近的 slot，而非全部页码 -->
              <div
                v-for="pageNum in renderableSlots"
                :key="pageNum"
                :data-page-number="pageNum"
                class="reader-page-slot"
                :style="{ height: renderer.pageHeights.value[pageNum - 1] ? renderer.pageHeights.value[pageNum - 1] + 'px' : 'auto' }"
              >
                <PdfPage
                  v-if="pagesToRenderSet.has(pageNum)"
                  :pdf-doc="pdfDocProxy"
                  :page-number="pageNum"
                  :scale="scale"
                  :container-width="containerWidth"
                  :highlight-text="pageNum === highlightTargetPage ? highlightText : undefined"
                  :search-matches="searchMatchesByPage.get(pageNum)"
                  :annotation-adapter="annotationAdapter"
                  @page-height="(h: number) => renderer.updatePageHeight(pageNum - 1, h)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, shallowRef, watch, nextTick, onBeforeUnmount, computed, provide, type Ref } from 'vue'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { usePdfjs } from '../composables/use-pdfjs'
import { usePdfRenderer, type ViewMode } from '../composables/use-pdf-renderer'
import { usePdfAnnotation } from '../composables/use-pdf-annotation'
import { usePdfSearch } from '../composables/use-pdf-search'
import { buildPaperOpenUrl } from '../services/library-api'
import PdfPage from './pdf-reader/PdfPage.vue'
import PdfToolbar from './pdf-reader/PdfToolbar.vue'
import PdfOutline from './pdf-reader/PdfOutline.vue'
import type { OutlineItem } from './pdf-reader/PdfOutline.vue'
import { usePdfKeyboard } from '../composables/use-pdf-keyboard'

const { lib: pdfjsLib, cMapOptions } = usePdfjs()

const props = defineProps<{
  visible: boolean
  paperId: string
  targetPage?: number
  highlightText?: string
  demoMode?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const highlightTargetPage = computed(() => props.targetPage)

const scrollContainerRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const paperTitle = ref('PDF 阅读器')
const scale = ref(1.0)
const containerWidth = ref(480)
const outlineOpen = ref(false)
const hasOutline = ref(false)
const outlineItems = ref<OutlineItem[]>([])
const viewMode = ref<ViewMode>('continuous')

// pdfjs-dist PDFDocumentProxy has JS private fields (#).
// shallowRef() stores the raw object without proxying — Vue's recommended pattern for class instances.
const pdfDocProxy = shallowRef<PDFDocumentProxy | null>(null) as Ref<PDFDocumentProxy | null>

const renderer = usePdfRenderer(pdfDocProxy, scale, viewMode)

// ── 通过 provide/inject 将缓存 API 传给 PdfPage ──
provide('getCachedCanvas', renderer.getCachedCanvas)
provide('setCachedCanvas', renderer.setCachedCanvas)

const { adapter: annotationAdapter } = usePdfAnnotation(renderer.scrollToPage)

// Search composable — pass reactive doc ref and scroll function
const search = usePdfSearch(pdfDocProxy, renderer.scrollToPage)

// ── 优化 4: 搜索匹配预计算为 Map，避免模板中每页调用函数 ──
const searchMatchesByPage = computed(() => {
  if (!search.isOpen.value || search.results.value.length === 0) return new Map<number, Array<{ charStart: number; charEnd: number; isCurrent: boolean }>>()
  const map = new Map<number, Array<{ charStart: number; charEnd: number; isCurrent: boolean }>>()
  const currentMatch = search.results.value[search.currentMatchIndex.value]
  for (const m of search.results.value) {
    const pageNum = m.pageIndex + 1
    if (!map.has(pageNum)) map.set(pageNum, [])
    map.get(pageNum)!.push({
      charStart: m.charStart,
      charEnd: m.charEnd,
      isCurrent: currentMatch != null && currentMatch.pageIndex === m.pageIndex && currentMatch.charStart === m.charStart,
    })
  }
  return map
})

// ── 优化 4: DOM 虚拟化 — 只渲染视口附近的 slot ──
const SLOT_BUFFER = 15
const renderableSlots = computed(() => {
  const total = renderer.totalPages.value
  if (total === 0) return []
  const center = renderer.currentPage.value
  const start = Math.max(1, center - SLOT_BUFFER)
  const end = Math.min(total, center + SLOT_BUFFER)
  const slots: number[] = []
  for (let i = start; i <= end; i++) slots.push(i)
  return slots
})

// O(1) Set 查询替代 Array.includes()
const pagesToRenderSet = computed(() => new Set(renderer.pagesToRender.value))

// ── 关键修复: renderableSlots 变化时重新注册 observer ──
watch(renderableSlots, async (newSlots, oldSlots) => {
  if (!scrollContainerRef.value || !pdfDocProxy.value) return
  await nextTick()
  const oldSet = new Set(oldSlots ?? [])
  const newSet = new Set(newSlots)
  // 注销已移除的 slot
  for (const p of oldSet) {
    if (!newSet.has(p)) renderer.unregisterPage(p)
  }
  // 注册新增的 slot
  for (const p of newSet) {
    if (!oldSet.has(p)) {
      const el = scrollContainerRef.value!.querySelector<HTMLElement>(`[data-page-number="${p}"]`)
      if (el) renderer.registerPage(p, el)
    }
  }
})

usePdfKeyboard({
  active: computed(() => props.visible),
  currentPage: renderer.currentPage,
  totalPages: renderer.totalPages,
  onClose: () => emit('close'),
  onScrollToPage: renderer.scrollToPage,
  onZoomIn: () => setScale(Math.min(3, scale.value + 0.25)),
  onZoomOut: () => setScale(Math.max(0.5, scale.value - 0.25)),
  onOpenSearch: () => search.openSearch(),
  onCloseSearch: () => search.closeSearch(),
  isSearchOpen: search.isOpen,
})

/** Navigation: step by 1 in single/continuous, step by 2 in double mode */
function goPrev() {
  const step = viewMode.value === 'double' ? 2 : 1
  renderer.scrollToPage(renderer.currentPage.value - step)
}
function goNext() {
  const step = viewMode.value === 'double' ? 2 : 1
  renderer.scrollToPage(renderer.currentPage.value + step)
}

/** Handle Escape from the panel div: close search if open, otherwise close panel */
function handleEscape() {
  if (search.isOpen.value) {
    search.closeSearch()
  } else {
    emit('close')
  }
}

function setScale(next: number) {
  scale.value = next
}

function setViewMode(mode: ViewMode) {
  viewMode.value = mode
}

async function loadPdf() {
  if (!props.paperId) return

  loading.value = true
  error.value = null
  pdfDocProxy.value = null
  renderer.totalPages.value = 0
  renderer.currentPage.value = 1

  try {
    const isDemo = props.demoMode || props.paperId.startsWith('paper-')
    const url = isDemo ? '/demo-paper.pdf' : buildPaperOpenUrl(props.paperId)
    const loadingTask = pdfjsLib.getDocument({ url, ...cMapOptions })
    pdfDocProxy.value = await loadingTask.promise
    paperTitle.value = isDemo ? 'Demo PDF' : 'PDF 预览'
    annotationAdapter.setDocument(pdfDocProxy.value)

    await renderer.init(pdfDocProxy.value)
    await loadOutline()

    if (props.targetPage && props.targetPage >= 1 && props.targetPage <= pdfDocProxy.value.numPages) {
      renderer.currentPage.value = props.targetPage
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'PDF 加载失败，请检查文件是否完整'
  } finally {
    loading.value = false
  }
}

async function loadOutline() {
  if (!pdfDocProxy.value) return
  const rawOutline = await pdfDocProxy.value.getOutline()
  if (!rawOutline || rawOutline.length === 0) {
    hasOutline.value = false
    outlineItems.value = []
    return
  }
  hasOutline.value = true

  const items: OutlineItem[] = []
  for (const raw of rawOutline) {
    items.push(await resolveOutlineItem(raw as { title: string; dest: unknown; items: unknown[] }))
  }
  outlineItems.value = items
}

async function resolveOutlineItem(raw: { title: string; dest: unknown; items: unknown[] }): Promise<OutlineItem> {
  let pageNumber: number | undefined
  try {
    let dest = raw.dest
    if (typeof dest === 'string') {
      dest = await pdfDocProxy.value!.getDestination(dest)
    }
    if (Array.isArray(dest) && dest.length > 0) {
      const pageIdx = await pdfDocProxy.value!.getPageIndex(dest[0])
      pageNumber = pageIdx + 1
    }
  } catch {
    // ignore unresolvable destinations
  }

  const children: OutlineItem[] = []
  if (raw.items && raw.items.length > 0) {
    for (const child of raw.items as Array<{ title: string; dest: unknown; items: unknown[] }>) {
      children.push(await resolveOutlineItem(child))
    }
  }

  return { title: raw.title, dest: raw.dest, items: children, pageNumber }
}

watch(() => props.visible, async (visible) => {
  if (visible && props.paperId) {
    await loadPdf()
    await nextTick()
    if (scrollContainerRef.value && pdfDocProxy.value) {
      // Register visible slot elements with the renderer
      const slots = scrollContainerRef.value.querySelectorAll<HTMLElement>('[data-page-number]')
      for (const slot of slots) {
        const pageNum = Number(slot.getAttribute('data-page-number'))
        if (!isNaN(pageNum)) renderer.registerPage(pageNum, slot)
      }
      renderer.setupObserver(scrollContainerRef.value)
    }
    if (props.targetPage && props.targetPage >= 1) {
      await nextTick()
      renderer.scrollToPage(props.targetPage)
    }
  } else {
    search.closeSearch()
    annotationAdapter.setDocument(null)
    pdfDocProxy.value?.destroy()
    pdfDocProxy.value = null
    renderer.clearCanvasCache()
  }
})

// 视图模式切换时：切回 continuous 需重建 observer
watch(viewMode, async (mode) => {
  if (mode === 'continuous' && scrollContainerRef.value && pdfDocProxy.value) {
    await nextTick()
    renderer.setupObserver(scrollContainerRef.value)
  }
})

onBeforeUnmount(() => {
  pdfDocProxy.value?.destroy()
  pdfDocProxy.value = null
})
</script>

<style scoped>
.reader-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.reader-backdrop-enter-active {
  transition: opacity 300ms ease-out;
}

.reader-backdrop-leave-active {
  transition: opacity 250ms ease-in-out;
}

.reader-backdrop-enter-from,
.reader-backdrop-leave-to {
  opacity: 0;
}

.reader-panel {
  position: fixed;
  inset: 0;
  z-index: 210;
  display: flex;
  flex-direction: column;
  background: var(--color-surface-card);
}

.reader-content {
  position: relative;
  flex: 1;
  display: flex;
  overflow: hidden;
}

.reader-panel-enter-active {
  transition: opacity 200ms ease-out;
}

.reader-panel-leave-active {
  transition: opacity 150ms ease-in-out;
}

.reader-panel-enter-from,
.reader-panel-leave-to {
  opacity: 0;
}

/* ── Shared button style (error retry) ── */
.reader-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  transition: background 0.15s, color 0.15s;
}

.reader-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

/* ── Body ── */
.reader-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
  background: var(--color-surface-muted);
  display: flex;
  justify-content: center;
}

/* Single page mode: hide overflow, center the single page */
.reader-body--single {
  overflow: hidden !important;
  align-items: center;
}

/* Double page mode: hide overflow, center the pair */
.reader-body--double {
  overflow: hidden !important;
  align-items: center;
}

.reader-pages {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-4) 0;
  gap: var(--space-3);
}

.reader-pages--double {
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  padding: var(--space-4);
}

.reader-pages--double .reader-page-slot {
  width: calc(50% - 6px);
  margin-bottom: 0;
}

.reader-page-slot {
  display: flex;
  justify-content: center;
  margin-bottom: var(--space-3);
}

.reader-canvas {
  background: white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  border-radius: 2px;
}

/* ── Loading / Error ── */
.reader-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  height: 100%;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.reader-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-border-subtle);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.reader-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  height: 100%;
  color: var(--color-error);
  font-size: var(--font-size-sm);
}
</style>
