/**
 * Lightweight inline markdown → HTML converter.
 * Designed to run AFTER escapeHtml() so that only known safe patterns
 * are turned back into HTML tags.
 *
 * Supported: **bold**, *italic*, `inline code`
 */

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
