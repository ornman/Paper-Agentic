import { ref, watch, onBeforeUnmount, type Ref } from 'vue'
import type { PDFDocumentProxy } from 'pdfjs-dist'

export type ViewMode = 'single' | 'double' | 'continuous'

export function usePdfRenderer(
  pdfDoc: Ref<PDFDocumentProxy | null>,
  scale: Ref<number>,
  viewMode: Ref<ViewMode>,
) {
  const currentPage = ref(1)
  const totalPages = ref(0)
  const pageHeights = ref<number[]>([])
  const visiblePages = ref<Set<number>>(new Set())

  const BUFFER_BEFORE = 2
  const BUFFER_AFTER = 2

  const pagesToRender = ref<number[]>([])

  let observer: IntersectionObserver | null = null
  const pageElements = new Map<number, HTMLElement>()

  async function init(doc: PDFDocumentProxy) {
    totalPages.value = doc.numPages
    currentPage.value = 1
    pageHeights.value = []
    await precomputeHeights(doc)
    updatePagesToRender()
  }

  async function precomputeHeights(doc: PDFDocumentProxy) {
    const heights: number[] = []
    const batchSize = 10
    for (let i = 1; i <= doc.numPages; i += batchSize) {
      const batch = []
      for (let j = i; j <= Math.min(i + batchSize - 1, doc.numPages); j++) {
        batch.push(doc.getPage(j))
      }
      const pages = await Promise.all(batch)
      for (const page of pages) {
        const vp = page.getViewport({ scale: scale.value * (96 / 72) })
        heights.push(vp.height)
      }
    }
    pageHeights.value = heights
  }

  function setupObserver(scrollContainer: HTMLElement) {
    // 只断开旧 observer，不清空 pageElements（调用方已注册）
    if (observer) {
      for (const el of pageElements.values()) {
        observer.unobserve(el)
      }
      observer.disconnect()
      observer = null
    }
    visiblePages.value.clear()

    // single/double 模式不需要 IntersectionObserver
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

  function updatePagesToRender() {
    const mode = viewMode.value

    if (mode === 'single') {
      pagesToRender.value = [currentPage.value]
      return
    }

    if (mode === 'double') {
      // 偶数起始：确保 spread 从奇数页开始
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
      // 双页模式：确保 spread 从奇数页开始
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

  watch(scale, async () => {
    if (pdfDoc.value) {
      await precomputeHeights(pdfDoc.value)
    }
  })

  // 视图模式切换时：重新计算渲染页，continuous 模式需重建 observer
  watch(viewMode, () => {
    if (viewMode.value !== 'continuous') {
      // 非 continuous 模式：断开 observer
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
  }
}
