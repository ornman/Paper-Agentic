<!-- frontend/src/components/pdf-reader/PdfPage.vue -->
<template>
  <div ref="containerRef" class="pdf-page" :data-page-number="pageNumber">
    <canvas ref="canvasRef" class="pdf-page-canvas" />
    <div ref="textLayerRef" class="textLayer" />
    <div ref="annotationLayerRef" class="annotationLayer" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy, PageViewport } from 'pdfjs-dist'
import type { AnnotationAdapter } from '../../composables/use-pdf-annotation'
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
    await renderAnnotationLayer()
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
 *
 * Algorithm:
 * 1. Build char-offset → TextItem mapping
 * 2. Locate the match range [matchStart, matchEnd) in the concatenated text
 * 3. For each TextItem overlapping the match range, compute its CSS bounding rect
 *    using the PDF transform + viewport coordinate conversion
 */
function computeHighlightRects(
  items: PdfTextItem[],
  matchStart: number,
  matchEnd: number,
  viewport: PageViewport,
): HighlightRect[] {
  // Build char-offset ranges for each TextItem
  let charOffset = 0
  const itemRanges: { item: PdfTextItem; start: number; end: number }[] = []
  for (const item of items) {
    const len = item.str.length
    itemRanges.push({ item, start: charOffset, end: charOffset + len })
    charOffset += len
  }

  const rects: HighlightRect[] = []

  for (const { item, start, end } of itemRanges) {
    // Check if this item overlaps with the match range
    if (end <= matchStart || start >= matchEnd) continue

    // How much of this item's text falls within the match
    const overlapStart = Math.max(start, matchStart) - start
    const overlapEnd = Math.min(end, matchEnd) - start
    const overlapRatio = (overlapEnd - overlapStart) / item.str.length

    // Transform: [scaleX, skewY, skewX, scaleY, tx, ty]
    // tx/ty are in PDF coordinate space (origin bottom-left)
    const [, , , d, tx, ty] = item.transform
    const [cssX, cssYFlipped] = viewport.convertToViewportPoint(tx, ty)
    // convertToViewportPoint flips Y so origin is top-left;
    // the returned Y is the *top* of the text line
    const fontSize = Math.abs(d) * viewport.scale
    const cssY = cssYFlipped - fontSize

    // Width proportional to the overlapping portion of the text
    const fullItemWidth = item.width * viewport.scale
    const rectWidth = fullItemWidth * overlapRatio
    // Offset X by the portion before the overlap
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

async function highlightOnPage() {
  if (!containerRef.value || !pageProxy || !currentViewport) return

  clearHighlightRects()

  // Phase 4 search mode: use pre-computed rects
  if (props.highlightRects && props.highlightRects.length > 0) {
    // Mark the "current" match index
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

  // Ctrl+F search mode: compute rects from searchMatches (char offsets)
  if (props.searchMatches && props.searchMatches.length > 0) {
    const textContent = await pageProxy.getTextContent()
    const textItems: PdfTextItem[] = textContent.items
      .filter((item) => 'str' in item)
      .map((item) => {
        const ti = item as unknown as PdfTextItem
        return {
          str: ti.str,
          transform: ti.transform,
          width: ti.width,
          height: ti.height,
        }
      })
      .filter((ti) => ti.str.length > 0)

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

  const textContent = await pageProxy.getTextContent()
  const textItems: PdfTextItem[] = textContent.items
    .filter((item) => 'str' in item)
    .map((item) => {
      const ti = item as unknown as PdfTextItem
      return {
        str: ti.str,
        transform: ti.transform,
        width: ti.width,
        height: ti.height,
      }
    })
    .filter((ti) => ti.str.length > 0)
  const fullText = textItems.map((item) => item.str).join('')

  const searchStr = props.highlightText.trim()
  const idx = fullText.indexOf(searchStr)

  if (idx === -1) {
    // No match: flash border to indicate the page was targeted but text not found
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
  () => render(),
)

watch(
  () => props.scale,
  () => render(),
)

// Re-render highlights when search rects or search matches change (without full re-render)
watch(
  () => [props.highlightRects, props.currentHighlightIndex, props.searchMatches] as const,
  () => highlightOnPage(),
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
