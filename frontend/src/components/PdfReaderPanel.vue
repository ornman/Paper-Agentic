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
        <PdfToolbar
          :title="paperTitle"
          :current-page="renderer.currentPage.value"
          :total-pages="renderer.totalPages.value"
          :scale="scale"
          :outline-open="outlineOpen"
          :show-outline-button="hasOutline"
          @close="emit('close')"
          @prev="renderer.scrollToPage(renderer.currentPage.value - 1)"
          @next="renderer.scrollToPage(renderer.currentPage.value + 1)"
          @zoom-in="setScale(Math.min(3, scale + 0.25))"
          @zoom-out="setScale(Math.max(0.5, scale - 0.25))"
          @go-to-page="renderer.scrollToPage"
          @toggle-outline="outlineOpen = !outlineOpen"
        />

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
import PdfToolbar from './pdf-reader/PdfToolbar.vue'

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

const scrollContainerRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const paperTitle = ref('PDF 阅读器')
const scale = ref(1.0)
const containerWidth = ref(480)
const outlineOpen = ref(false)
const hasOutline = ref(false)

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
