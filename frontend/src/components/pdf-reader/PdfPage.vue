<!-- frontend/src/components/pdf-reader/PdfPage.vue -->
<template>
  <div
    ref="containerRef"
    class="pdf-page"
    :data-page-number="pageNumber"
  >
    <canvas ref="canvasRef" class="pdf-page-canvas" />
    <div ref="textLayerRef" class="pdf-text-layer" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy, PageViewport } from 'pdfjs-dist'

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
const canvasRef = ref<HTMLCanvasElement | null>(null)
const textLayerRef = ref<HTMLDivElement | null>(null)

let renderTask: { promise: Promise<void>; cancel(): void } | null = null
let pageProxy: PDFPageProxy | null = null

async function render() {
  if (!canvasRef.value) return

  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }

  try {
    pageProxy = await props.pdfDoc.getPage(props.pageNumber)
    const dpr = window.devicePixelRatio || 1
    const viewport = pageProxy.getViewport({ scale: props.scale * dpr })
    const displayViewport = pageProxy.getViewport({ scale: props.scale })
    const canvas = canvasRef.value

    canvas.width = viewport.width
    canvas.height = viewport.height
    canvas.style.width = `${Math.floor(displayViewport.width)}px`
    canvas.style.height = `${Math.floor(displayViewport.height)}px`

    emit('page-height', Math.floor(displayViewport.height))

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    renderTask = pageProxy.render({ canvas, canvasContext: ctx, viewport })
    await renderTask.promise

    await renderTextLayer(pageProxy, displayViewport)

    if (props.highlightText) {
      await highlightOnPage()
    }
  } catch (e: unknown) {
    if (e instanceof Error && e.name === 'RenderingCancelledException') return
    console.error(`Page ${props.pageNumber} render error:`, e)
  } finally {
    renderTask = null
  }
}

async function renderTextLayer(page: PDFPageProxy, viewport: PageViewport) {
  if (!textLayerRef.value) return

  const textContent = await page.getTextContent()
  const textLayer = new TextLayer({
    textContentSource: textContent,
    container: textLayerRef.value,
    viewport,
  })
  await textLayer.render()
}

async function highlightOnPage() {
  if (!props.highlightText || !pageProxy || !containerRef.value) return

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

watch(
  () => [props.pdfDoc, props.pageNumber, props.scale] as const,
  () => render(),
  { immediate: true },
)

onBeforeUnmount(() => {
  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }
  pageProxy?.cleanup()
})
</script>

<style scoped>
.pdf-page {
  position: relative;
  background: white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  border-radius: 2px;
  margin: 0 auto;
}

.pdf-page-canvas {
  display: block;
}

.pdf-text-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
  opacity: 0.25;
  line-height: 1;
}

.pdf-text-layer ::selection {
  background: var(--color-accent-soft);
}

.pdf-text-layer > span {
  color: transparent;
  position: absolute;
  white-space: pre;
  transform-origin: 0% 0%;
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
