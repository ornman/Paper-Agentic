// frontend/src/composables/use-pdf-renderer.ts
import { ref, watch, onBeforeUnmount, type Ref } from 'vue'
import type { PDFDocumentProxy } from 'pdfjs-dist'

export type ViewMode = 'single' | 'double' | 'continuous'

/** OffscreenCanvas 缓存条目 */
export interface CachedCanvas {
  canvas: OffscreenCanvas
  width: number
  height: number
  scale: number
}

/** 单个缓存条目的最大像素数，超过则跳过缓存（防止 GPU 内存爆炸） */
const MAX_CACHE_PIXELS = 4_000_000 // ~16 MB RGBA

export function usePdfRenderer(
  _pdfDoc: Ref<PDFDocumentProxy | null>,
  scale: Ref<number>,
  viewMode: Ref<ViewMode>,
) {
  const currentPage = ref(1)
  const totalPages = ref(0)

  /**
   * 用 ref（深度追踪）+ 原地修改，避免 shallowRef 每次赋值复制整个数组。
   * 200 个 number 的深度追踪开销远小于每次 [...arr] 复制。
   */
  const pageHeights = ref<number[]>([])

  const visiblePages = ref<Set<number>>(new Set())

  const BUFFER_BEFORE = 2
  const BUFFER_AFTER = 2

  const pagesToRender = ref<number[]>([])

  let observer: IntersectionObserver | null = null
  const pageElements = new Map<number, HTMLElement>()

  // ── 优化 1: 懒加载高度 ──
  let lastKnownAverageHeight = 800 // CSS px，首页加载后修正

  // ── 优化 2: Canvas LRU 缓存 ──
  const canvasCache = new Map<number, CachedCanvas>()
  const CANVAS_CACHE_MAX = 10

  const PDF_TO_CSS_UNITS = 96 / 72

  // ────────────────────────────────────────
  //  Canvas 缓存 API
  // ────────────────────────────────────────

  function getCachedCanvas(pageNum: number): CachedCanvas | null {
    const cached = canvasCache.get(pageNum)
    if (!cached) return null
    // scale 不匹配则失效
    if (cached.scale !== scale.value) {
      canvasCache.delete(pageNum)
      return null
    }
    return cached
  }

  function setCachedCanvas(pageNum: number, entry: CachedCanvas): void {
    // 像素预算检查：防止高缩放 + 高 DPR 导致 GPU 内存爆炸
    const pixelCount = entry.width * entry.height
    if (pixelCount > MAX_CACHE_PIXELS) return

    // LRU 淘汰
    if (canvasCache.size >= CANVAS_CACHE_MAX) {
      const oldest = canvasCache.keys().next().value
      if (oldest !== undefined) canvasCache.delete(oldest)
    }
    // 若已存在则先删再插，移到最新位置
    canvasCache.delete(pageNum)
    canvasCache.set(pageNum, entry)
  }

  function clearCanvasCache(): void {
    canvasCache.clear()
  }

  // ────────────────────────────────────────
  //  初始化（懒加载高度）
  // ────────────────────────────────────────

  async function init(doc: PDFDocumentProxy) {
    totalPages.value = doc.numPages
    currentPage.value = 1

    // 仅加载第 1 页获取参考高度，而非全部页
    const page1 = await doc.getPage(1)
    const vp = page1.getViewport({ scale: scale.value * PDF_TO_CSS_UNITS })
    lastKnownAverageHeight = vp.height
    page1.cleanup()

    // 用估算高度填充，确保初始布局立刻可用
    pageHeights.value = Array(doc.numPages).fill(lastKnownAverageHeight)
    updatePagesToRender()
  }

  /** 由 PdfPage 渲染后回调，原地更新精确高度 */
  function updatePageHeight(index: number, height: number) {
    if (pageHeights.value[index] === height) return
    pageHeights.value[index] = height // ref 深度追踪，原地修改即可触发响应
  }

  // ────────────────────────────────────────
  //  IntersectionObserver
  // ────────────────────────────────────────

  function setupObserver(scrollContainer: HTMLElement) {
    if (observer) {
      for (const el of pageElements.values()) {
        observer.unobserve(el)
      }
      observer.disconnect()
      observer = null
    }
    visiblePages.value.clear()

    if (viewMode.value !== 'continuous') {
      updatePagesToRender()
      return
    }

    observer = new IntersectionObserver(
      (entries) => {
        let topPage = currentPage.value
        let topY = Infinity

        for (const entry of entries) {
          const pageNum = Number(entry.target.getAttribute('data-page-number'))
          if (isNaN(pageNum)) continue

          if (entry.isIntersecting) {
            visiblePages.value.add(pageNum)
            if (entry.boundingClientRect.top < topY) {
              topY = entry.boundingClientRect.top
              topPage = pageNum
            }
          } else {
            visiblePages.value.delete(pageNum)
          }
        }

        if (topPage !== currentPage.value) {
          currentPage.value = topPage
        }

        updatePagesToRender()
      },
      {
        root: scrollContainer,
        threshold: 0.1,
      },
    )

    for (const el of pageElements.values()) {
      observer.observe(el)
    }
  }

  function registerPage(pageNum: number, el: HTMLElement) {
    pageElements.set(pageNum, el)
    observer?.observe(el)
  }

  function unregisterPage(pageNum: number) {
    const el = pageElements.get(pageNum)
    if (el) {
      observer?.unobserve(el)
      pageElements.delete(pageNum)
    }
  }

  function teardownObserver() {
    if (observer) {
      for (const el of pageElements.values()) {
        observer.unobserve(el)
      }
      observer.disconnect()
      observer = null
    }
    pageElements.clear()
    visiblePages.value.clear()
  }

  // ────────────────────────────────────────
  //  渲染页计算
  // ────────────────────────────────────────

  function updatePagesToRender() {
    const mode = viewMode.value

    if (mode === 'single') {
      pagesToRender.value = [currentPage.value]
      return
    }

    if (mode === 'double') {
      let start = currentPage.value
      if (start % 2 === 0) {
        start = start - 1
      }
      const end = Math.min(start + 1, totalPages.value)
      const pages: number[] = []
      for (let i = start; i <= end; i++) {
        pages.push(i)
      }
      pagesToRender.value = pages
      return
    }

    // continuous 模式：可见页 ± buffer
    const pages = new Set<number>()
    const visible = Array.from(visiblePages.value)

    if (visible.length === 0) {
      for (
        let i = Math.max(1, currentPage.value - BUFFER_BEFORE);
        i <= Math.min(totalPages.value, currentPage.value + BUFFER_AFTER);
        i++
      ) {
        pages.add(i)
      }
    } else {
      for (const vp of visible) {
        for (
          let i = Math.max(1, vp - BUFFER_BEFORE);
          i <= Math.min(totalPages.value, vp + BUFFER_AFTER);
          i++
        ) {
          pages.add(i)
        }
      }
    }

    pagesToRender.value = Array.from(pages).sort((a, b) => a - b)
  }

  function scrollToPage(pageNum: number) {
    if (pageNum < 1 || pageNum > totalPages.value) return

    const mode = viewMode.value

    if (mode === 'single') {
      currentPage.value = pageNum
      updatePagesToRender()
      return
    }

    if (mode === 'double') {
      let spreadStart = pageNum
      if (spreadStart % 2 === 0) {
        spreadStart = spreadStart - 1
      }
      spreadStart = Math.max(1, spreadStart)
      currentPage.value = spreadStart
      updatePagesToRender()
      return
    }

    // continuous 模式：scrollIntoView
    const el = pageElements.get(pageNum)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    currentPage.value = pageNum
  }

  // ── scale watcher：只清缓存，不重置高度（避免竞态覆盖已修正高度） ──
  // PdfPage 重新渲染后会通过 updatePageHeight 回调修正，无需预先重置
  watch(scale, () => {
    clearCanvasCache()
  })

  // 视图模式切换时：重新计算渲染页，continuous 模式需重建 observer
  watch(viewMode, () => {
    if (viewMode.value !== 'continuous') {
      if (observer) {
        for (const el of pageElements.values()) {
          observer.unobserve(el)
        }
        observer.disconnect()
        observer = null
      }
      visiblePages.value.clear()
    }
    updatePagesToRender()
  })

  onBeforeUnmount(() => {
    clearCanvasCache()
    teardownObserver()
  })

  return {
    currentPage,
    totalPages,
    pageHeights,
    pagesToRender,
    visiblePages,
    viewMode,
    init,
    setupObserver,
    registerPage,
    unregisterPage,
    scrollToPage,
    updatePageHeight,
    getCachedCanvas,
    setCachedCanvas,
    clearCanvasCache,
  }
}
