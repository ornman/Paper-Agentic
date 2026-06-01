import type { SourceCard } from '../types/source'
import type { CitationAnnotation } from '../types/content'
import { renderInlineMarkdown } from './markdown-inline'

/** 最小 HTML 转义，防止 v-html XSS */
export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** 渲染内联 Markdown（粗体、斜体、行内代码），先转义再转换 */
export function renderInline(text: string | undefined): string {
  if (!text) return ''
  return renderInlineMarkdown(escapeHtml(text))
}

export interface NumberedSource {
  source: SourceCard
  num: number
}

/**
 * 基于后端精确偏移量的引用渲染。
 * 将 clean text 按 offset 切分为 N+1 段，每段独立做 escapeHtml + inline markdown，
 * 段间插入 <sup> 标记。
 */
export function renderParagraphWithExactCitations(
  text: string | undefined,
  citations: CitationAnnotation[],
  sources: SourceCard[],
): string {
  if (!text) return ''
  if (!citations.length) return renderInlineMarkdown(escapeHtml(text))

  // 按 offset 升序排列
  const sorted = [...citations].sort((a, b) => a.offset - b.offset)

  // 构建 sourceId → 编号 的映射（1-based）
  const sourceNumMap = new Map<string, number>()
  for (let i = 0; i < sources.length; i++) {
    sourceNumMap.set(sources[i].id, i + 1)
  }

  const parts: string[] = []
  let prevOffset = 0

  for (const cite of sorted) {
    const offset = Math.min(cite.offset, text.length)
    // 偏移前的文本段
    const segment = text.slice(prevOffset, offset)
    parts.push(renderInlineMarkdown(escapeHtml(segment)))

    // 引用标记
    const num = sourceNumMap.get(cite.sourceId) ?? '?'
    parts.push(
      `<sup class="cite-marker" data-source-id="${escapeHtml(cite.sourceId)}">[${num}]</sup>`,
    )

    prevOffset = offset
  }

  // 尾部剩余文本
  const tail = text.slice(prevOffset)
  parts.push(renderInlineMarkdown(escapeHtml(tail)))

  return parts.join('')
}

/**
 * 启发式引用渲染（降级用）。
 * 策略：在句末标点（。！？；.!?) 后插入可点击的 <sup>[N]</sup>，
 * 引用来源轮询分配，每段最多 2 个标记。
 */
export function renderParagraphWithCitations(
  text: string | undefined,
  numberedSources: NumberedSource[],
): string {
  if (!text) return ''
  if (numberedSources.length === 0) return renderInlineMarkdown(escapeHtml(text))

  const escaped = renderInlineMarkdown(escapeHtml(text))

  // 找到所有句末位置
  const sentenceEndRe = /[。！？；.!?]/g
  const endPositions: number[] = []
  let m: RegExpExecArray | null
  while ((m = sentenceEndRe.exec(escaped)) !== null) {
    endPositions.push(m.index + m[0].length)
  }

  if (endPositions.length === 0) {
    // 无句末标点 — 在末尾放一个标记
    const { source, num } = numberedSources[0]
    const marker = `<sup class="cite-marker" data-source-id="${escapeHtml(source.id)}">[${num}]</sup>`
    return escaped + marker
  }

  // 轮询分配引用，每段最多 2 个
  const maxMarkers = Math.min(2, numberedSources.length)
  const markers: Array<{ pos: number; html: string }> = []

  for (let i = 0; i < maxMarkers; i++) {
    const endIdx = endPositions[Math.min(i, endPositions.length - 1)]
    const { source, num } = numberedSources[i % numberedSources.length]
    const markerHtml = `<sup class="cite-marker" data-source-id="${escapeHtml(source.id)}">[${num}]</sup>`
    markers.push({ pos: endIdx, html: markerHtml })
  }

  // 从后往前插入，保持位置不变
  let result = escaped
  for (let i = markers.length - 1; i >= 0; i--) {
    const { pos, html } = markers[i]
    result = result.slice(0, pos) + html + result.slice(pos)
  }

  return result
}
