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

  // ─── 过滤器选项聚合 ───────────────────────────────────

  const yearOptions = computed(() => {
    const years = new Set<string>()
    for (const p of papers()) {
      if (p.year != null) years.add(String(p.year))
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

  // ─── 搜索 ──────────────────────────────────────────────

  const fuseInstance = computed(() => new Fuse(papers(), fuseOptions))

  const fuseResults = computed(() => {
    const q = query.value.trim()
    if (!q) return []
    return fuseInstance.value.search(q)
  })

  const hasQuery = computed(() => query.value.trim().length > 0)

  // ─── 过滤 + 排序 ──────────────────────────────────────

  const results = computed(() => {
    let list: PaperItem[]
    if (hasQuery.value) {
      list = fuseResults.value.map((r) => r.item)
    } else {
      list = [...papers()]
    }

    // 年份过滤（year 现在是 number | null）
    if (yearFilter.value) {
      const filterYear = yearFilter.value
      list = list.filter((p) => p.year != null && String(p.year) === filterYear)
    }

    // 作者过滤
    if (authorFilter.value) {
      const filterAuthor = authorFilter.value
      list = list.filter((p) =>
        p.authors
          .split(/[,;、]/)
          .map((a) => a.trim())
          .includes(filterAuthor),
      )
    }

    // 排序
    if (hasQuery.value && sortBy.value === 'relevance') {
      // Fuse 结果已按相关性排序
    } else {
      list.sort((a, b) => {
        switch (sortBy.value) {
          case 'title':
            return a.title.localeCompare(b.title)
          case 'year':
            return (b.year ?? 0) - (a.year ?? 0)
          case 'time':
          default:
            return new Date(b.import_time).getTime() - new Date(a.import_time).getTime()
        }
      })
    }

    return list
  })

  const totalResults = computed(() => results.value.length)

  // ─── 搜索高亮 ─────────────────────────────────────────

  function escapeHtml(str: string): string {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  function highlightText(text: string): string {
    const q = query.value.trim()
    if (!q) return escapeHtml(text)
    const safeText = escapeHtml(text)
    const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return safeText.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>')
  }

  // ─── 重置 ──────────────────────────────────────────────

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
    highlightText,
    resetFilters,
  }
}
