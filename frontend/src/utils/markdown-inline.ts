/**
 * Lightweight markdown → HTML converters.
 *
 * - renderInlineMarkdown: handles **bold**, *italic*, `code` (for block content)
 * - renderStreamingMarkdown: lightweight block+inline for streaming preview
 *
 * All functions expect already-HTML-escaped input (via escapeHtml)
 * so that only known safe patterns are turned back into HTML tags.
 */

// ── Inline patterns (operate on escaped text) ──

const BOLD_RE = /\*\*(.+?)\*\*/g
const ITALIC_RE = /(?<!\*)\*([^*]+?)\*(?!\*)/g
const CODE_RE = /`([^`]+?)`/g

export function renderInlineMarkdown(escaped: string): string {
  let result = escaped
  // Bold first (so italic regex doesn't eat ** markers)
  result = result.replace(BOLD_RE, '<strong>$1</strong>')
  result = result.replace(ITALIC_RE, '<em>$1</em>')
  result = result.replace(CODE_RE, '<code class="inline-code">$1</code>')
  return result
}

// ── Streaming renderer ──
// Handles block-level structures commonly seen in LLM output during streaming:
// headings, ordered/unordered lists, code fences, blockquotes, paragraphs.

const HEADING_RE = /^(#{1,4})\s+(.+)$/
const ORDERED_LIST_RE = /^(\d+)\.\s+(.*)$/
const UNORDERED_LIST_RE = /^[-*]\s+(.*)$/
const BLOCKQUOTE_RE = /^>\s?(.*)$/
const CODE_FENCE_OPEN_RE = /^```(\w*)$/
const CODE_FENCE_CLOSE_RE = /^```\s*$/

/**
 * Render streaming text with lightweight block-level markdown support.
 * Produces safe HTML for v-html consumption.
 * Intentionally simple — full block parsing happens server-side via ContentBlock events.
 */
export function renderStreamingMarkdown(escaped: string): string {
  const lines = escaped.split('\n')
  const htmlParts: string[] = []
  let inCodeFence = false
  let codeLines: string[] = []
  let inList = false
  let listOrdered = false
  let listItems: string[] = []

  const flushList = () => {
    if (listItems.length === 0) return
    const tag = listOrdered ? 'ol' : 'ul'
    const cls = listOrdered
      ? 'block-list block-list--ordered'
      : 'block-list'
    const items = listItems
      .map((item) => `<li>${renderInlineMarkdown(item)}</li>`)
      .join('')
    htmlParts.push(`<${tag} class="${cls}">${items}</${tag}>`)
    listItems = []
    inList = false
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // ── Code fence handling ──
    if (inCodeFence) {
      if (CODE_FENCE_CLOSE_RE.test(line)) {
        const code = codeLines.join('\n')
        htmlParts.push(`<pre class="block-code"><code>${code}</code></pre>`)
        codeLines = []
        inCodeFence = false
      } else {
        codeLines.push(line)
      }
      continue
    }

    const fenceOpen = CODE_FENCE_OPEN_RE.exec(line)
    if (fenceOpen) {
      flushList()
      inCodeFence = true
      codeLines = []
      continue
    }

    // ── Heading ──
    const headingMatch = HEADING_RE.exec(line)
    if (headingMatch) {
      flushList()
      const level = Math.min(headingMatch[1].length, 4)
      const text = renderInlineMarkdown(headingMatch[2].trim())
      const tag = `h${level}`
      const cls = level === 2 ? 'block-heading' : `block-heading block-heading--h${level}`
      htmlParts.push(`<${tag} class="${cls}">${text}</${tag}>`)
      continue
    }

    // ── Ordered list ──
    const orderedMatch = ORDERED_LIST_RE.exec(line)
    if (orderedMatch) {
      if (inList && !listOrdered) flushList()
      inList = true
      listOrdered = true
      listItems.push(orderedMatch[2].trim())
      continue
    }

    // ── Unordered list ──
    const unorderedMatch = UNORDERED_LIST_RE.exec(line)
    if (unorderedMatch) {
      if (inList && listOrdered) flushList()
      inList = true
      listOrdered = false
      listItems.push(unorderedMatch[1].trim())
      continue
    }

    // ── Blockquote ──
    const quoteMatch = BLOCKQUOTE_RE.exec(line)
    if (quoteMatch) {
      flushList()
      const text = renderInlineMarkdown(quoteMatch[1].trim())
      htmlParts.push(`<blockquote class="block-blockquote">${text}</blockquote>`)
      continue
    }

    // ── Empty line → paragraph break ──
    if (line.trim() === '') {
      flushList()
      // Don't emit empty paragraphs
      continue
    }

    // ── Plain text → paragraph ──
    flushList()
    htmlParts.push(`<p class="block-paragraph">${renderInlineMarkdown(line)}</p>`)
  }

  // Flush remaining list
  flushList()

  // Unclosed code fence → show what we have
  if (inCodeFence && codeLines.length > 0) {
    const code = codeLines.join('\n')
    htmlParts.push(`<pre class="block-code"><code>${code}</code></pre>`)
  }

  return htmlParts.join('')
}
