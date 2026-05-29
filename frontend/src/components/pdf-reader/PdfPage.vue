<!-- frontend/src/components/pdf-reader/PdfPage.vue -->
<template>
  <div ref="containerRef" class="pdf-page" :data-page-number="pageNumber">
    <canvas ref="canvasRef" class="pdf-page-canvas" />
    <div ref="textLayerRef" class="pdf-text-layer" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

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
const canvasRef = ref<HTMLCanvasElement | null>(null)
const textLayerRef = ref<HTMLDivElement | null>(null)

let renderTask: { promise: Promise<void>; cancel(): void } | null = null
let pageProxy: PDFPageProxy | null = null

async function render() {
  if (!canvasRef.value || !textLayerRef.value) return

  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }

  try {
    pageProxy = await props.pdfDoc.getPage(props.pageNumber)
    const dpr = window.devicePixelRatio || 1
    const viewport = pageProxy.getViewport({ scale: props.scale * PDF_TO_CSS_UNITS })
    const canvas = canvasRef.value

    const actualWidth = Math.floor(viewport.width)
    const actualHeight = Math.floor(viewport.height)

    canvas.width = actualWidth * dpr
    canvas.height = actualHeight * dpr
    canvas.style.width = `${actualWidth}px`
    canvas.style.height = `${actualHeight}px`

    emit('page-height', actualHeight)

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.save()
    ctx.scale(dpr, dpr)
    renderTask = pageProxy.render({
      canvas,
      canvasContext: ctx,
      viewport,
    })
    await renderTask.promise
    ctx.restore()

    await renderTextLayer()
  } catch (e: unknown) {
    if (e instanceof Error && e.name === 'RenderingCancelledException') return
    console.error(`Page ${props.pageNumber} render error:`, e)
  } finally {
    renderTask = null
  }
}

async function renderTextLayer() {
  if (!textLayerRef.value || !pageProxy) return

  // Clear previous text layer
  textLayerRef.value.innerHTML = ''

  const viewport = pageProxy.getViewport({ scale: props.scale * PDF_TO_CSS_UNITS })
  const textContent = await pageProxy.getTextContent()

  const textLayer = new TextLayer({
    textContentSource: textContent,
    container: textLayerRef.value,
    viewport,
  })
  await textLayer.render()

  if (props.highlightText) {
    highlightOnPage()
  }
}

async function highlightOnPage() {
  if (!props.highlightText || !containerRef.value || !pageProxy) return

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
  containerRef.value.appendChild(overlay)

  setTimeout(() => {
    overlay.classList.add('pdf-highlight-fadeout')
    setTimeout(() => overlay.remove(), 3000)
  }, 3000)
}

onMounted(() => render())

watch(
  () => [props.pdfDoc, props.pageNumber] as const,
  () => render(),
)

watch(
  () => props.scale,
  () => render(),
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
  opacity: 0.2;
  line-height: 1;
}

.pdf-text-layer ::selection {
  background: var(--color-accent-soft, rgba(59, 130, 246, 0.25));
}

.pdf-text-layer > :deep(span) {
  color: transparent;
  position: absolute;
  white-space: pre;
  transform-origin: 0% 0%;
}

.pdf-highlight-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
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
