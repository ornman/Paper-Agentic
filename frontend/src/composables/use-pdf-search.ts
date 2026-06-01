// frontend/src/composables/use-pdf-search.ts
import { ref, computed, watch, onBeforeUnmount, type Ref, type ComputedRef } from 'vue'
import type { PDFDocumentProxy } from 'pdfjs-dist'

/** Subset of pdfjs-dist TextItem used for text extraction */
interface PdfTextItem {
  str: string
  transform: number[]
  width: number
  height: number
}

interface PageTextCache {
  text: string
  items: PdfTextItem[]
}

export interface SearchMatch {
  /** 0-based page index */
  pageIndex: number
  /** Start char offset within the page's concatenated text */
  charStart: number
  /** End char offset (exclusive) */
  charEnd: number
  /** Matched text snippet */
  text: string
}

export function usePdfSearch(
  pdfDoc: Ref<PDFDocumentProxy | null>,
  scrollToPage: (page: number) => void,
): {
  query: Ref<string>
  isOpen: Ref<boolean>
  results: Ref<SearchMatch[]>
  currentMatchIndex: Ref<number>
  matchCount: ComputedRef<number>
  openSearch: () => void
  closeSearch: () => void
  search: (q: string) => Promise<void>
  nextMatch: () => void
  prevMatch: () => void
} {
  const query = ref('')
  const isOpen = ref(false)
  const results = ref<SearchMatch[]>([])
  const currentMatchIndex = ref(-1)
  const matchCount = computed(() => results.value.length)

  /** Lazy page text cache, keyed by 0-based page index */
  const textCache = new Map<number, PageTextCache>()

  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  /** Extract text + items for a single page (lazy, cached) */
  async function getPageText(pageIndex: number): Promise<PageTextCache | null> {
    if (textCache.has(pageIndex)) {
      return textCache.get(pageIndex)!
    }

    const doc = pdfDoc.value
    if (!doc) return null

    try {
      const page = await doc.getPage(pageIndex + 1) // pdfjs is 1-based
      const textContent = await page.getTextContent()
      const items: PdfTextItem[] = textContent.items
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

      const text = items.map((item) => item.str).join('')
      const cache: PageTextCache = { text, items }
      textCache.set(pageIndex, cache)
      return cache
    } catch {
      return null
    }
  }

  /** Perform the actual search across all pages */
  async function performSearch(searchQuery: string): Promise<void> {
    if (!searchQuery.trim()) {
      results.value = []
      currentMatchIndex.value = -1
      return
    }

    const doc = pdfDoc.value
    if (!doc) {
      results.value = []
      currentMatchIndex.value = -1
      return
    }

    const allMatches: SearchMatch[] = []
    const searchStr = searchQuery.trim().toLowerCase()

    for (let pageIdx = 0; pageIdx < doc.numPages; pageIdx++) {
      const cache = await getPageText(pageIdx)
      if (!cache) continue

      const pageTextLower = cache.text.toLowerCase()
      let searchOffset = 0

      while (searchOffset < pageTextLower.length) {
        const idx = pageTextLower.indexOf(searchStr, searchOffset)
        if (idx === -1) break

        allMatches.push({
          pageIndex: pageIdx,
          charStart: idx,
          charEnd: idx + searchStr.length,
          text: cache.text.substring(idx, idx + searchStr.length),
        })

        searchOffset = idx + 1
      }
    }

    results.value = allMatches
    currentMatchIndex.value = allMatches.length > 0 ? 0 : -1

    // Scroll to first match
    if (allMatches.length > 0) {
      scrollToPage(allMatches[0].pageIndex + 1)
    }
  }

  /** Debounced search entry point (300ms) */
  async function search(q: string): Promise<void> {
    query.value = q

    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }

    if (!q.trim()) {
      results.value = []
      currentMatchIndex.value = -1
      return
    }

    debounceTimer = setTimeout(() => {
      performSearch(q)
    }, 300)
  }

  function nextMatch(): void {
    if (results.value.length === 0) return
    const next = (currentMatchIndex.value + 1) % results.value.length
    currentMatchIndex.value = next
    const match = results.value[next]
    scrollToPage(match.pageIndex + 1)
  }

  function prevMatch(): void {
    if (results.value.length === 0) return
    const prev =
      currentMatchIndex.value <= 0
        ? results.value.length - 1
        : currentMatchIndex.value - 1
    currentMatchIndex.value = prev
    const match = results.value[prev]
    scrollToPage(match.pageIndex + 1)
  }

  function openSearch(): void {
    isOpen.value = true
  }

  function closeSearch(): void {
    isOpen.value = false
    query.value = ''
    results.value = []
    currentMatchIndex.value = -1
  }

  // Invalidate cache when document changes
  watch(pdfDoc, () => {
    textCache.clear()
    results.value = []
    currentMatchIndex.value = -1
  })

  onBeforeUnmount(() => {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    textCache.clear()
  })

  return {
    query,
    isOpen,
    results,
    currentMatchIndex,
    matchCount,
    openSearch,
    closeSearch,
    search,
    nextMatch,
    prevMatch,
  }
}
