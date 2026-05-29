<!-- frontend/src/components/pdf-reader/PdfPage.vue -->
<template>
  <div ref="containerRef" class="pdf-page" :data-page-number="pageNumber" />
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, inject } from 'vue'
import { PDFPageView } from 'pdfjs-dist/web/pdf_viewer.mjs'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'
import type { EventBus } from 'pdfjs-dist/web/pdf_viewer.mjs'
import 'pdfjs-dist/web/pdf_viewer.css'
import { PDF_EVENT_BUS_KEY } from '../../composables/pdf-event-bus'

const PDF_TO_CSS_UNITS = 96 / 72

const props = defineProps<{
  pdfDoc: PDFDocumentProxy
  pageNumber: number
  scale: number
  containerWidth: number
  highlightText?: string
}>()

const emit = defineEmits<{
  (e: 'page-height', height: number): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const eventBus = inject(PDF_EVENT_BUS_KEY) as EventBus

let pageView: PDFPageView | null = null

async function createAndDraw() {
  if (!containerRef.value) return

  destroyPageView()

  const pageProxy = await props.pdfDoc.getPage(props.pageNumber)
  // 匹配官方 viewer 的 scale 模型：viewport = getViewport({ scale: scale * PDF_TO_CSS_UNITS })
  const viewport = pageProxy.getViewport({ scale: props.scale * PDF_TO_CSS_UNITS })

  emit('page-height', Math.floor(viewport.height))

  pageView = new PDFPageView({
    container: containerRef.value,
    eventBus,
    id: props.pageNumber,
    scale: props.scale,
    defaultViewport: viewport,
  })

  pageView.setPdfPage(pageProxy)
  await pageView.draw()

  if (props.highlightText) {
    highlightOnPage(pageProxy)
  }
}

function destroyPageView() {
  if (!pageView) return
  pageView.cancelRendering()
  pageView.destroy()
  pageView.div.remove()
  pageView = null
}

async function highlightOnPage(pageProxy: PDFPageProxy) {
  if (!props.highlightText || !containerRef.value) return

  const textContent = await pageProxy.getTextContent()
  const fullText = textContent.items
    .map((item) => ('str' in item ? item.str : ''))
    .join('')

  const searchStr = props.highlightText.trim()
  const idx = fullText.indexOf(searchStr)

  if (idx === -1) {
    containerRef.value.classList.add('pdf-page-flash')
    setTimeout(() => containerRef.value?.classList.remove('pdf-page-flash'), 2000)
    return
  }

  const overlay = document.createElement('div')
  overlay.className = 'pdf-highlight-overlay'
  overlay.style.position = 'absolute'
  overlay.style.top = '0'
  overlay.style.left = '0'
  overlay.style.right = '0'
  overlay.style.bottom = '0'
  overlay.style.pointerEvents = 'none'
  containerRef.value.appendChild(overlay)

  setTimeout(() => {
    overlay.classList.add('pdf-highlight-fadeout')
    setTimeout(() => overlay.remove(), 3000)
  }, 3000)
}

onMounted(() => createAndDraw())

watch(
  () => [props.pdfDoc, props.pageNumber] as const,
  () => createAndDraw(),
)

watch(
  () => props.scale,
  () => {
    if (!pageView) return
    pageView.update({ scale: props.scale })
    const viewport = pageView.viewport
    if (viewport) {
      emit('page-height', Math.floor(viewport.height))
    }
  },
)

onBeforeUnmount(() => {
  destroyPageView()
})
</script>

<style scoped>
.pdf-page {
  position: relative;
  background: white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  border-radius: 2px;
  margin: 0 auto;
  --scale-round-x: 1px;
  --scale-round-y: 1px;
  --total-scale-factor: var(--scale-factor);
}

.pdf-page :deep(.page) {
  box-shadow: none !important;
  margin: 0 !important;
}

.pdf-page :deep(canvas) {
  display: block;
}

.pdf-highlight-overlay {
  background: rgba(59, 130, 246, 0.15);
  animation: highlight-pulse 0.3s ease-out;
}

@keyframes highlight-pulse {
  from { background: rgba(59, 130, 246, 0.3); }
  to { background: rgba(59, 130, 246, 0.15); }
}

.pdf-highlight-fadeout {
  animation: highlight-fade 3s ease-out forwards;
}

@keyframes highlight-fade {
  from { opacity: 1; }
  to { opacity: 0; }
}

.pdf-page-flash {
  animation: page-flash-border 0.5s ease-out 3;
}

@keyframes page-flash-border {
  0%, 100% { box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08); }
  50% { box-shadow: 0 0 0 2px var(--color-accent); }
}
</style>
