<!-- frontend/src/components/pdf-reader/PdfPage.vue -->
<template>
  <div ref="containerRef" class="pdf-page" :data-page-number="pageNumber">
    <canvas ref="canvasRef" class="pdf-page-canvas" />
    <div ref="textLayerRef" class="textLayer" />
    <div ref="annotationLayerRef" class="annotationLayer" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, inject } from 'vue'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy, PageViewport } from 'pdfjs-dist'
import type { AnnotationAdapter } from '../../composables/use-pdf-annotation'
import type { CachedCanvas } from '../../composables/use-pdf-renderer'
import 'pdfjs-dist/web/pdf_viewer.css'

const PDF_TO_CSS_UNITS = 96 / 72

/**
 * Subset of pdfjs-dist TextItem fields used for highlight computation.
 * Defined locally because pdfjs-dist does not re-export TextItem from its top-level.
 */
interface PdfTextItem {
  str: string
  transform: number[]
  width: number
  height: number
}

/** Extract typed PdfTextItem[] from pdfjs TextContent */
function extractTextItems(textContent: { items: Array<Record<string, unknown>> }): PdfTextItem[] {
  return textContent.items
    .filter((item: Record<string, unknown>) => 'str' in item)
    .map((item: Record<string, unknown>) => ({
      str: item.str as string,
      transform: item.transform as number[],
      width: item.width as number,
      height: item.height as number,
    }))
    .filter((ti: PdfTextItem) => ti.str.length > 0)
}

/** A highlight rectangle in CSS-pixel coordinates relative to the page container */
export interface HighlightRect {
  x: number
  y: number
  width: number
  height: number
}

/** A search match on this page, with char offsets into the page's concatenated text */
export interface SearchMatchOnPage {
  charStart: number
  charEnd: number
  /** Whether this match is the currently-selected one */
  isCurrent: boolean
}

const props = defineProps<{
  pdfDoc: PDFDocumentProxy
  pageNumber: number
  scale: number
  containerWidth: number
  highlightText?: string
  /** Pre-computed highlight rects (e.g. from search) */
  highlightRects?: HighlightRect[]
  /** Index of the "current" search match among highlightRects */
  currentHighlightIndex?: number
  /** Search matches for this page with char offsets (Ctrl+F results) */
  searchMatches?: SearchMatchOnPage[]
  annotationAdapter?: AnnotationAdapter
}>()

const emit = defineEmits<{
  (e: 'page-height', height: number): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const textLayerRef = ref<HTMLDivElement | null>(null)
const annotationLayerRef = ref<HTMLDivElement | null>(null)

let renderTask: { promise: Promise<void>; cancel(): void } | null = null
let pageProxy: PDFPageProxy | null = null
/** Shared viewport — computed once, reused by canvas and TextLayer */
let currentViewport: PageViewport | null = null

// ── 优化 3: 缓存 textContent，避免同页重复调用 ──
let lastTextContent: Awaited<ReturnType<PDFPageProxy['getTextContent']>> | null = null

/** Renderer 的缓存 API — 通过 inject 获取 */
const getCachedCanvas = inject<((pageNum: number) => CachedCanvas | null) | null>('getCachedCanvas', null)
const setCachedCanvas = inject<((pageNum: number, entry: CachedCanvas) => void) | null>('setCachedCanvas', null)

async function render() {
  if (!canvasRef.value || !textLayerRef.value || !containerRef.value) return

  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }

  try {
    pageProxy = await props.pdfDoc.getPage(props.pageNumber)
    const dpr = window.devicePixelRatio || 1

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

    container.style.setProperty('--scale-factor', String(currentViewport.scale))
    container.style.setProperty('--user-unit', '1')
    container.style.setProperty('--total-scale-factor', String(currentViewport.scale))

    container.style.width = `${actualWidth}px`
    container.style.height = `${actualHeight}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // ── 优化 2: 检查 Canvas 缓存 ──
    const cached = getCachedCanvas?.(props.pageNumber)
    if (cached && cached.width === actualWidth && cached.height === actualHeight) {
      // 缓存命中：直接 drawImage，<1ms
      ctx.save()
      ctx.drawImage(cached.canvas, 0, 0, actualWidth, actualHeight)
      ctx.restore()
    } else {
      // 缓存未命中：完整渲染
      ctx.save()
      ctx.scale(dpr, dpr)
      renderTask = pageProxy.render({
        canvas,
        canvasContext: ctx,
        viewport: currentViewport,
      })
      await renderTask.promise
      ctx.restore()

      // 渲染后存入缓存（利用 OffscreenCanvas）
      try {
        const offscreen = new OffscreenCanvas(actualWidth * dpr, actualHeight * dpr)
        const offCtx = offscreen.getContext('2d')
        if (offCtx) {
          offCtx.drawImage(canvas, 0, 0)
          setCachedCanvas?.(props.pageNumber, {
            canvas: offscreen,
            width: actualWidth,
            height: actualHeight,
            scale: props.scale,
          })
        }
      } catch {
        // OffscreenCanvas 不可用时静默跳过缓存
      }
    }

    await renderTextLayer()
    await renderAnnotationLayer()
  } catch (e: unknown) {
    // RenderingCancelledException 是正常的取消操作，静默处理
    if (e instanceof Error && e.name === 'RenderingCancelledException') return
    // 其他渲染错误也静默处理，避免虚拟列表频繁 mount/unmount 时刷屏
  } finally {
    renderTask = null
  }
}

async function renderTextLayer() {
  if (!textLayerRef.value || !pageProxy || !currentViewport) return

  // Clear previous text layer
  textLayerRef.value.innerHTML = ''

  // 优化 3: 缓存 textContent 供后续 highlightOnPage 复用
  lastTextContent = await pageProxy.getTextContent()

  const textLayer = new TextLayer({
    textContentSource: lastTextContent,
    container: textLayerRef.value,
    viewport: currentViewport,
  })
  await textLayer.render()

  // 渲染 textLayer 后直接调高亮（复用 lastTextContent）
  if (props.highlightText || (props.highlightRects && props.highlightRects.length > 0) || (props.searchMatches && props.searchMatches.length > 0)) {
    highlightOnPage()
  }
}

async function renderAnnotationLayer() {
  if (!annotationLayerRef.value || !pageProxy || !currentViewport) return
  if (!props.annotationAdapter) return

  try {
    await props.annotationAdapter.renderAnnotations(
      pageProxy,
      currentViewport,
      annotationLayerRef.value,
    )
  } catch {
    // Annotation layer rendering failed — silently skip
  }
}

/**
 * Compute precise highlight rectangles for a text match within a set of PDF TextItems.
 */
function computeHighlightRects(
  items: PdfTextItem[],
  matchStart: number,
  matchEnd: number,
  viewport: PageViewport,
): HighlightRect[] {
  let charOffset = 0
  const itemRanges: { item: PdfTextItem; start: number; end: number }[] = []
  for (const item of items) {
    const len = item.str.length
    itemRanges.push({ item, start: charOffset, end: charOffset + len })
    charOffset += len
  }

  const rects: HighlightRect[] = []

  for (const { item, start, end } of itemRanges) {
    if (end <= matchStart || start >= matchEnd) continue

    const overlapStart = Math.max(start, matchStart) - start
    const overlapEnd = Math.min(end, matchEnd) - start
    const overlapRatio = (overlapEnd - overlapStart) / item.str.length

    const [, , , d, tx, ty] = item.transform
    const [cssX, cssYFlipped] = viewport.convertToViewportPoint(tx, ty)
    const fontSize = Math.abs(d) * viewport.scale
    const cssY = cssYFlipped - fontSize

    const fullItemWidth = item.width * viewport.scale
    const rectWidth = fullItemWidth * overlapRatio
    const rectX = cssX + fullItemWidth * (overlapStart / item.str.length)

    rects.push({
      x: rectX,
      y: cssY,
      width: rectWidth,
      height: fontSize,
    })
  }

  return rects
}

/** Remove existing highlight rect DOM elements from the container */
function clearHighlightRects() {
  if (!containerRef.value) return
  const existing = containerRef.value.querySelectorAll('.pdf-highlight-rect')
  existing.forEach((el) => el.remove())
}

/** Render highlight rects as absolutely-positioned divs */
function renderHighlightRects(rects: HighlightRect[], autoFade: boolean) {
  if (!containerRef.value) return

  for (let i = 0; i < rects.length; i++) {
    const r = rects[i]
    const el = document.createElement('div')
    el.className = 'pdf-highlight-rect'
    el.style.left = `${r.x}px`
    el.style.top = `${r.y}px`
    el.style.width = `${r.width}px`
    el.style.height = `${r.height}px`
    containerRef.value.appendChild(el)
  }

  if (autoFade) {
    setTimeout(() => {
      const elements = containerRef.value?.querySelectorAll('.pdf-highlight-rect')
      elements?.forEach((el) => {
        el.classList.add('pdf-highlight-rect--fadeout')
        el.addEventListener('animationend', () => el.remove())
      })
    }, 3000)
  }
}

function highlightOnPage() {
  if (!containerRef.value || !pageProxy || !currentViewport) return

  clearHighlightRects()

  // Phase 4 search mode: use pre-computed rects
  if (props.highlightRects && props.highlightRects.length > 0) {
    const rects = props.highlightRects
    for (let i = 0; i < rects.length; i++) {
      const r = rects[i]
      const el = document.createElement('div')
      el.className = 'pdf-highlight-rect pdf-highlight-rect--search'
      if (i === props.currentHighlightIndex) {
        el.classList.add('pdf-highlight-rect--current')
      }
      el.style.left = `${r.x}px`
      el.style.top = `${r.y}px`
      el.style.width = `${r.width}px`
      el.style.height = `${r.height}px`
      containerRef.value.appendChild(el)
    }
    return
  }

  // 优化 3: 复用 lastTextContent，避免重复调用 getTextContent()
  // Ctrl+F search mode: compute rects from searchMatches (char offsets)
  if (props.searchMatches && props.searchMatches.length > 0) {
    const textContent = lastTextContent
    if (!textContent) return

    const textItems = extractTextItems(textContent)

    for (const match of props.searchMatches) {
      const rects = computeHighlightRects(textItems, match.charStart, match.charEnd, currentViewport)
      for (const r of rects) {
        const el = document.createElement('div')
        el.className = 'pdf-highlight-rect pdf-highlight-rect--search'
        if (match.isCurrent) {
          el.classList.add('pdf-highlight-rect--current')
        }
        el.style.left = `${r.x}px`
        el.style.top = `${r.y}px`
        el.style.width = `${r.width}px`
        el.style.height = `${r.height}px`
        containerRef.value.appendChild(el)
      }
    }
    return
  }

  // Citation highlight mode: compute rects from highlightText
  if (!props.highlightText) return

  const textContent = lastTextContent
  if (!textContent) return

  const textItems = extractTextItems(textContent)
  const fullText = textItems.map((item) => item.str).join('')

  const searchStr = props.highlightText.trim()
  const idx = fullText.indexOf(searchStr)

  if (idx === -1) {
    containerRef.value.classList.add('pdf-page-flash')
    setTimeout(() => containerRef.value?.classList.remove('pdf-page-flash'), 2000)
    return
  }

  const rects = computeHighlightRects(textItems, idx, idx + searchStr.length, currentViewport)
  renderHighlightRects(rects, true)
}

onMounted(() => render())

watch(
  () => [props.pdfDoc, props.pageNumber] as const,
  () => {
    lastTextContent = null
    render()
  },
)

// ── 优化 6: 缩放防抖 150ms ──
let scaleDebounce: ReturnType<typeof setTimeout> | null = null
watch(
  () => props.scale,
  () => {
    if (scaleDebounce) clearTimeout(scaleDebounce)
    scaleDebounce = setTimeout(() => {
      lastTextContent = null
      render()
    }, 150)
  },
)

// Re-render highlights when search rects or search matches change (without full re-render)
watch(
  () => [props.highlightRects, props.currentHighlightIndex, props.searchMatches] as const,
  () => highlightOnPage(),
)

onBeforeUnmount(() => {
  if (scaleDebounce) clearTimeout(scaleDebounce)
  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }
  currentViewport = null
  lastTextContent = null
  pageProxy?.cleanup()
  pageProxy = null
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

.annotationLayer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.annotationLayer :deep(a) {
  pointer-events: auto;
}

/* pdf_viewer.css handles all .textLayer / .textLayer span positioning & sizing */

.pdf-highlight-rect {
  position: absolute;
  background: rgba(59, 130, 246, 0.25);
  pointer-events: none;
  border-radius: 2px;
  z-index: 1;
}

/* Search match highlight — yellow per spec */
.pdf-highlight-rect--search {
  background: rgba(255, 255, 0, 0.35);
}

/* Current match highlight (used during search navigation) */
.pdf-highlight-rect--current {
  background: rgba(251, 146, 60, 0.4);
}

/* Citation highlight auto-fade */
.pdf-highlight-rect--fadeout {
  animation: highlight-rect-fade 3s ease-out forwards;
}

@keyframes highlight-rect-fade {
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
  CSS 防护
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
