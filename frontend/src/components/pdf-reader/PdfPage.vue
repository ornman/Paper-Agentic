<!-- frontend/src/components/pdf-reader/PdfPage.vue -->
<template>
  <div ref="containerRef" class="pdf-page" :data-page-number="pageNumber">
    <canvas ref="canvasRef" class="pdf-page-canvas" />
    <div ref="textLayerRef" class="textLayer" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy, PageViewport } from 'pdfjs-dist'
import 'pdfjs-dist/web/pdf_viewer.css'

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
/** Shared viewport — computed once, reused by canvas and TextLayer */
let currentViewport: PageViewport | null = null

async function render() {
  if (!canvasRef.value || !textLayerRef.value || !containerRef.value) return

  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }

  try {
    pageProxy = await props.pdfDoc.getPage(props.pageNumber)
    const dpr = window.devicePixelRatio || 1

    // ── 改动 1.1: 共享 viewport，只计算一次 ──
    currentViewport = pageProxy.getViewport({ scale: props.scale * PDF_TO_CSS_UNITS })
    const canvas = canvasRef.value
    const container = containerRef.value

    const actualWidth = Math.floor(currentViewport.width)
    const actualHeight = Math.floor(currentViewport.height)

    canvas.width = actualWidth * dpr
    canvas.height = actualHeight * dpr
    canvas.style.width = `${actualWidth}px`
    canvas.style.height = `${actualHeight}px`

    emit('page-height', actualHeight)

    // ── 改动 1.2: 在容器上设置 CSS 变量 ──
    // pdf_viewer.css 的 TextLayer span 使用 --total-scale-factor 计算 font-size
    container.style.setProperty('--scale-factor', String(currentViewport.scale))
    container.style.setProperty('--user-unit', '1')
    container.style.setProperty('--total-scale-factor', String(currentViewport.scale))

    // ── 改动 1.3: 显式设置容器尺寸 ──
    container.style.width = `${actualWidth}px`
    container.style.height = `${actualHeight}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.save()
    ctx.scale(dpr, dpr)
    renderTask = pageProxy.render({
      canvas,
      canvasContext: ctx,
      viewport: currentViewport,
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
  if (!textLayerRef.value || !pageProxy || !currentViewport) return

  // Clear previous text layer
  textLayerRef.value.innerHTML = ''

  const textContent = await pageProxy.getTextContent()

  const textLayer = new TextLayer({
    textContentSource: textContent,
    container: textLayerRef.value,
    viewport: currentViewport,
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
  currentViewport = null
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

/* pdf_viewer.css handles all .textLayer / .textLayer span positioning & sizing */

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

<!--
  改动 1.4: CSS 防护
  非 scoped — pdf_viewer.css 的选择器（如 .pdfViewer .page）需要匹配这些类名。
  这里用 .pdf-page 作为自定义容器类名，提供 pdf_viewer.css 期望的 CSS 变量回退。
-->
<style>
.pdf-page {
  --user-unit: 1;
  --total-scale-factor: calc(var(--scale-factor, 1) * var(--user-unit, 1));
  box-sizing: content-box; /* 防止全局 border-box 干扰尺寸计算 */
}
</style>
