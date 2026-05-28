<!-- frontend/src/components/pdf-reader/PdfPage.vue -->
<template>
  <div
    ref="containerRef"
    class="pdf-page"
    :data-page-number="pageNumber"
  >
    <canvas ref="canvasRef" class="pdf-page-canvas" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

const props = defineProps<{
  pdfDoc: PDFDocumentProxy
  pageNumber: number
  scale: number
  containerWidth: number
}>()

const emit = defineEmits<{
  (e: 'page-height', height: number): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

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
    const canvas = canvasRef.value

    canvas.width = viewport.width
    canvas.height = viewport.height
    canvas.style.width = `${Math.floor(viewport.width / dpr)}px`
    canvas.style.height = `${Math.floor(viewport.height / dpr)}px`

    emit('page-height', Math.floor(viewport.height / dpr))

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    renderTask = pageProxy.render({ canvasContext: ctx, viewport })
    await renderTask.promise
  } catch (e: unknown) {
    if (e instanceof Error && e.name === 'RenderingCancelledException') return
    console.error(`Page ${props.pageNumber} render error:`, e)
  } finally {
    renderTask = null
  }
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
</style>
