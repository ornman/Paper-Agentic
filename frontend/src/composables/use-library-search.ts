import { ref, computed } from 'vue'
import Fuse, { type IFuseOptions } from 'fuse.js'
import type { PaperItem } from '../types/paper'

export type SortMode = 'relevance' | 'time' | 'year' | 'title'


const fuseOptions: IFuseOptions<PaperItem> = {
  keys: [
    { name: 'title', weight: 0.5 },
    { name: 'authors', weight: 0.3 },
    { name: 'keywords', weight: 0.2 },
  ],
  threshold: 0.4,
  includeScore: true,
  ignoreLocation: true,
}

export function useLibrarySearch(papers: () => PaperItem[]) {
  const query = ref('')
  const yearFilter = ref('')
  const authorFilter = ref('')
  const sortBy = ref<SortMode>('time')

  // --- Aggregations for filter dropdowns ---

  const yearOptions = computed(() => {
    const years = new Set<string>()
    for (const p of papers()) {
      if (p.year) years.add(p.year)
    }
    return [...years].sort().reverse()
  })

  const authorOptions = computed(() => {
    const map = new Map<string, number>()
    for (const p of papers()) {
      if (!p.authors) continue
      for (const a of p.authors.split(/[,;、]/)) {
        const name = a.trim()
        if (name) map.set(name, (map.get(name) ?? 0) + 1)
      }
    }
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([name]) => name)
  })

  // --- Search ---

  const fuseInstance = computed(() => new Fuse(papers(), fuseOptions))

  const fuseResults = computed(() => {
    const q = query.value.trim()
    if (!q) return []
    return fuseInstance.value.search(q)
  })

  const hasQuery = computed(() => query.value.trim().length > 0)

  // --- Filtered + sorted ---

  const results = computed(() => {
    // Base list: fuse results or all papers
    let list: PaperItem[]
    if (hasQuery.value) {
      list = fuseResults.value.map((r) => r.item)
    } else {
      list = [...papers()]
    }

    // Year filter
    if (yearFilter.value) {
      list = list.filter((p) => p.year === yearFilter.value)
    }

    // Author filter
    if (authorFilter.value) {
      list = list.filter((p) =>
        p.authors
          .split(/[,;、]/)
          .map((a) => a.trim())
          .includes(authorFilter.value),
      )
    }

    // Sort
    if (hasQuery.value && sortBy.value === 'relevance') {
      // Already in relevance order from fuse
    } else {
      list.sort((a, b) => {
        switch (sortBy.value) {
          case 'title':
            return a.title.localeCompare(b.title)
          case 'year':
            return (b.year ?? '').localeCompare(a.year ?? '')
          case 'time':
          default:
            return new Date(b.import_time).getTime() - new Date(a.import_time).getTime()
        }
      })
    }

    return list
  })

  const totalResults = computed(() => results.value.length)

  // --- Find similar ---

  function findSimilar(paperId: string): PaperItem[] {
    const target = papers().find((p) => p.paper_id === paperId)
    if (!target) return []

    const targetKeywords = new Set(target.keywords.map((k) => k.toLowerCase()))
    if (targetKeywords.size === 0) return []

    const scored = papers()
      .filter((p) => p.paper_id !== paperId)
      .map((p) => {
        const overlap = p.keywords.filter((k) => targetKeywords.has(k.toLowerCase())).length
        return { paper: p, score: overlap }
      })
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)

    return scored.map((s) => s.paper)
  }

  // --- Highlight helper ---

  function highlightText(text: string): string {
    const q = query.value.trim()
    if (!q) return escapeHtml(text)
    // Escape HTML first to prevent XSS via v-html
    const safeText = escapeHtml(text)
    const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return safeText.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>')
  }

  function escapeHtml(str: string): string {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  // --- Reset filters ---

  function resetFilters() {
    query.value = ''
    yearFilter.value = ''
    authorFilter.value = ''
  }

  return {
    query,
    yearFilter,
    authorFilter,
    sortBy,
    yearOptions,
    authorOptions,
    results,
    totalResults,
    hasQuery,
    findSimilar,
    highlightText,
    resetFilters,
  }
}
