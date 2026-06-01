/**
 * Lightweight inline markdown → HTML + streaming block parser.
 *
 * - renderInlineMarkdown: handles **bold**, *italic*, `code` (for block content)
 * - parseStreamingBlocks: parses raw markdown text into ContentBlock[] for
 *   unified rendering with the same Vue template used for server-parsed blocks.
 *
 * renderInlineMarkdown operates on already-HTML-escaped text (via escapeHtml)
 * so that only known safe patterns are turned back into HTML tags.
 */

import type { ContentBlock } from '../types/content'

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

// ── Streaming block parser ──
// Produces ContentBlock[] from raw markdown text, matching the same structure
// that the backend's stream_to_blocks() generates. This allows the frontend
// to use a single Vue template for both streaming and final rendering.

const HEADING_RE = /^(#{1,4})\s+(.+)$/
const ORDERED_LIST_RE = /^(\d+)\.\s+(.*)$/
const UNORDERED_LIST_RE = /^[-*]\s+(.*)$/
const BLOCKQUOTE_RE = /^>\s?(.*)$/
const CODE_FENCE_OPEN_RE = /^```(\w*)$/
const CODE_FENCE_CLOSE_RE = /^```\s*$/

/**
 * Parse raw markdown text into ContentBlock[] for streaming preview.
 * Output is structurally identical to backend's stream_to_blocks(),
 * so the same Vue template renders both without visual jump.
 */
export function parseStreamingBlocks(rawText: string): ContentBlock[] {
  const lines = rawText.split('\n')
  const blocks: ContentBlock[] = []
  let inCodeFence = false
  let codeLang = ''
  let codeLines: string[] = []
  let listOrdered = false
  let listItems: string[] = []

  const flushList = () => {
    if (listItems.length === 0) return
    blocks.push({ type: 'list', ordered: listOrdered, items: [...listItems] })
    listItems = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // ── Code fence handling ──
    if (inCodeFence) {
      if (CODE_FENCE_CLOSE_RE.test(line)) {
        blocks.push({
          type: 'code',
          language: codeLang || undefined,
          code: codeLines.join('\n'),
        })
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
      codeLang = fenceOpen[1] || ''
      codeLines = []
      continue
    }

    // ── Heading ──
    const headingMatch = HEADING_RE.exec(line)
    if (headingMatch) {
      flushList()
      blocks.push({
        type: 'heading',
        level: Math.min(headingMatch[1].length, 4),
        text: headingMatch[2].trim(),
      })
      continue
    }

    // ── Ordered list ──
    const orderedMatch = ORDERED_LIST_RE.exec(line)
    if (orderedMatch) {
      if (listOrdered === false && listItems.length > 0) flushList()
      listOrdered = true
      listItems.push(orderedMatch[2].trim())
      continue
    }

    // ── Unordered list ──
    const unorderedMatch = UNORDERED_LIST_RE.exec(line)
    if (unorderedMatch) {
      if (listOrdered === true && listItems.length > 0) flushList()
      listOrdered = false
      listItems.push(unorderedMatch[1].trim())
      continue
    }

    // ── Blockquote ──
    const quoteMatch = BLOCKQUOTE_RE.exec(line)
    if (quoteMatch) {
      flushList()
      blocks.push({ type: 'blockquote', text: quoteMatch[1].trim() })
      continue
    }

    // ── Empty line → break ──
    if (line.trim() === '') {
      flushList()
      continue
    }

    // ── Plain text → paragraph ──
    flushList()
    blocks.push({ type: 'paragraph', text: line.trim() })
  }

  // Flush remaining list
  flushList()

  // Unclosed code fence → emit what we have (streaming may still be writing)
  if (inCodeFence && codeLines.length > 0) {
    blocks.push({
      type: 'code',
      language: codeLang || undefined,
      code: codeLines.join('\n'),
    })
  }

  return blocks
}
