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
              :disabled="renderer.currentPage.value <= 1"
              aria-label="上一页"
              @click="renderer.scrollToPage(renderer.currentPage.value - 1)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
            </button>

            <span class="reader-page-info">
              <input
                ref="pageInputRef"
                class="reader-page-input"
                type="number"
                :value="renderer.currentPage.value"
                :min="1"
                :max="renderer.totalPages.value"
                @keydown.enter="handlePageInput"
                @blur="handlePageInput"
              />
              <span class="reader-page-sep">/</span>
              <span>{{ renderer.totalPages.value }}</span>
            </span>

            <button
              class="reader-btn"
              :disabled="renderer.currentPage.value >= renderer.totalPages.value"
              aria-label="下一页"
              @click="renderer.scrollToPage(renderer.currentPage.value + 1)"
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
        <div ref="scrollContainerRef" class="reader-body">
          <div v-if="loading" class="reader-loading">
            <div class="reader-spinner" />
            <span>加载中…</span>
          </div>
          <div v-else-if="error" class="reader-error">
            <span>{{ error }}</span>
            <button class="reader-btn" @click="loadPdf">重试</button>
          </div>
          <div v-else-if="pdfDocProxy" class="reader-pages">
            <div
              v-for="pageNum in renderer.totalPages.value"
              :key="pageNum"
              :data-page-number="pageNum"
              class="reader-page-slot"
              :style="{ height: renderer.pageHeights.value[pageNum - 1] ? renderer.pageHeights.value[pageNum - 1] + 'px' : 'auto' }"
            >
              <PdfPage
                v-if="renderer.pagesToRender.value.includes(pageNum)"
                :pdf-doc="pdfDocProxy"
                :page-number="pageNum"
                :scale="scale"
                :container-width="containerWidth"
                @page-height="(h: number) => onPageHeight(pageNum, h)"
              />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount, computed } from 'vue'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { usePdfjs } from '../composables/use-pdfjs'
import { usePdfRenderer } from '../composables/use-pdf-renderer'
import { buildPaperOpenUrl } from '../services/library-api'
import PdfPage from './pdf-reader/PdfPage.vue'

const { lib: pdfjsLib, cMapOptions } = usePdfjs()

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
const scrollContainerRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const paperTitle = ref('PDF 阅读器')
const scale = ref(1.0)
const containerWidth = ref(480)

let pdfDocProxy: PDFDocumentProxy | null = null

const renderer = usePdfRenderer(
  computed(() => pdfDocProxy),
  scale,
)

function onPageHeight(pageNum: number, height: number) {
  if (renderer.pageHeights.value[pageNum - 1] !== height) {
    renderer.pageHeights.value[pageNum - 1] = height
  }
}

function setScale(next: number) {
  scale.value = next
}

async function loadPdf() {
  if (!props.paperId) return

  loading.value = true
  error.value = null
  pdfDocProxy = null
  renderer.totalPages.value = 0
  renderer.currentPage.value = 1

  try {
    const isDemo = props.demoMode || props.paperId.startsWith('paper-')
    const url = isDemo ? '/demo-paper.pdf' : buildPaperOpenUrl(props.paperId)
    const loadingTask = pdfjsLib.getDocument({ url, ...cMapOptions })
    pdfDocProxy = await loadingTask.promise
    paperTitle.value = isDemo ? 'Demo PDF' : `PDF (${props.paperId.slice(0, 8)}…)`

    renderer.init(pdfDocProxy)

    if (props.targetPage && props.targetPage >= 1 && props.targetPage <= pdfDocProxy.numPages) {
      renderer.currentPage.value = props.targetPage
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'PDF 加载失败'
  } finally {
    loading.value = false
  }
}

function handlePageInput() {
  const val = parseInt(pageInputRef.value?.value ?? '', 10)
  if (!isNaN(val)) renderer.scrollToPage(val)
}

watch(() => props.visible, async (visible) => {
  if (visible && props.paperId) {
    await loadPdf()
    await nextTick()
    if (scrollContainerRef.value && pdfDocProxy) {
      // Register all page-slot elements with the renderer before setting up observer
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
    pdfDocProxy?.destroy()
    pdfDocProxy = null
  }
})

onBeforeUnmount(() => {
  pdfDocProxy?.destroy()
  pdfDocProxy = null
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
