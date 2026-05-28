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
        @keydown.escape="emit('close')"
      >
        <!-- Toolbar -->
        <div class="reader-toolbar">
          <div class="reader-title" :title="paperTitle">{{ paperTitle }}</div>

          <div class="reader-controls">
            <button
              class="reader-btn"
              :disabled="currentPage <= 1"
              aria-label="上一页"
              @click="goToPage(currentPage - 1)"
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
              @click="goToPage(currentPage + 1)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </button>

            <span class="reader-divider" />

            <button
              class="reader-btn"
              :disabled="scale <= 0.5"
              aria-label="缩小"
              @click="setScale(Math.max(0.5, scale - 0.25))"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </button>

            <span class="reader-scale-label">{{ Math.round(scale * 100) }}%</span>

            <button
              class="reader-btn"
              :disabled="scale >= 3"
              aria-label="放大"
              @click="setScale(Math.min(3, scale + 0.25))"
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

        <!-- PDF viewport -->
        <div class="reader-body" @scroll="onScroll">
          <div v-if="loading" class="reader-loading">
            <div class="reader-spinner" />
            <span>加载中…</span>
          </div>
          <div v-else-if="error" class="reader-error">
            <span>{{ error }}</span>
            <button class="reader-btn" @click="loadPdf">重试</button>
          </div>
          <div v-else class="reader-pages" :style="{ width: pageWidth + 'px' }">
            <canvas
              v-for="p in renderedPages"
              :key="p"
              :ref="(el) => setCanvasRef(p, el as HTMLCanvasElement | null)"
              class="reader-canvas"
              :style="{ width: pageWidth + 'px' }"
            />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick, onBeforeUnmount } from 'vue'
import { usePdfjs } from '../composables/use-pdfjs'
import { buildPaperOpenUrl } from '../services/library-api'

const { lib: pdfjsLib, cMapOptions } = usePdfjs()

const BUFFER = 1

const props = defineProps<{
  visible: boolean
  paperId: string
  targetPage?: number
  demoMode?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const pageInputRef = ref<HTMLInputElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const paperTitle = ref('PDF 阅读器')
const currentPage = ref(1)
const totalPages = ref(0)
const scale = ref(1.0)

let pdfDoc: pdfjsLib.PDFDocumentProxy | null = null
const canvasRefs = new Map<number, HTMLCanvasElement>()
const renderedSet = new Set<number>()

const pageWidth = computed(() => {
  return Math.floor(480 * scale.value)
})

const renderedPages = computed(() => {
  if (totalPages.value === 0) return []
  const pages: number[] = []
  const start = Math.max(1, currentPage.value - BUFFER)
  const end = Math.min(totalPages.value, currentPage.value + BUFFER)
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})

function setCanvasRef(page: number, el: HTMLCanvasElement | null) {
  if (el) canvasRefs.set(page, el)
  else canvasRefs.delete(page)
}

async function loadPdf() {
  if (!props.paperId) return

  loading.value = true
  error.value = null
  pdfDoc = null
  totalPages.value = 0
  currentPage.value = 1
  canvasRefs.clear()
  renderedSet.clear()

  try {
    const isDemo = props.demoMode || props.paperId.startsWith('paper-')
    const url = isDemo ? '/demo-paper.pdf' : buildPaperOpenUrl(props.paperId)
    const loadingTask = pdfjsLib.getDocument({ url, ...cMapOptions })
    pdfDoc = await loadingTask.promise
    totalPages.value = pdfDoc.numPages
    paperTitle.value = isDemo ? `Demo PDF` : `PDF (${props.paperId.slice(0, 8)}…)`
    if (props.targetPage && props.targetPage >= 1 && props.targetPage <= pdfDoc.numPages) {
      currentPage.value = props.targetPage
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'PDF 加载失败'
  } finally {
    loading.value = false
  }
}

async function renderPage(pageNum: number) {
  if (!pdfDoc || renderedSet.has(pageNum)) return
  const canvas = canvasRefs.get(pageNum)
  if (!canvas) return

  renderedSet.add(pageNum)
  const page = await pdfDoc.getPage(pageNum)
  const viewport = page.getViewport({ scale: scale.value * (window.devicePixelRatio || 1) })

  canvas.width = viewport.width
  canvas.height = viewport.height
  canvas.style.height = Math.floor(viewport.height / (window.devicePixelRatio || 1)) + 'px'

  const ctx = canvas.getContext('2d')
  if (!ctx) return
  await page.render({ canvas, canvasContext: ctx, viewport }).promise
}

async function renderVisiblePages() {
  for (const p of renderedPages.value) {
    await renderPage(p)
  }
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
}

function handlePageInput() {
  const val = parseInt(pageInputRef.value?.value ?? '', 10)
  if (!isNaN(val)) goToPage(val)
}

function onScroll() {
  // Determine current page from scroll position
}

function setScale(next: number) {
  renderedSet.clear()
  scale.value = next
}

watch(() => props.visible, async (visible) => {
  if (visible && props.paperId) {
    await loadPdf()
    await nextTick()
    await renderVisiblePages()
  } else {
    pdfDoc = null
    totalPages.value = 0
    canvasRefs.clear()
    renderedSet.clear()
  }
})

watch(currentPage, async () => {
  await nextTick()
  await renderVisiblePages()
})

watch(scale, async () => {
  await nextTick()
  await renderVisiblePages()
})

onBeforeUnmount(() => {
  pdfDoc?.destroy()
  pdfDoc = null
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

/* ── Toolbar ── */
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

/* ── Body ── */
.reader-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
  background: var(--color-surface-muted);
  display: flex;
  justify-content: center;
}

.reader-pages {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-4) 0;
  gap: var(--space-3);
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
