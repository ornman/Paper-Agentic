<template>
  <div class="ai-message">
    <!-- Thinking section (collapsible) -->
    <div v-if="message.thinking" class="thinking-section">
      <button
        class="thinking-toggle"
        :aria-expanded="thinkingExpanded"
        @click="thinkingExpanded = !thinkingExpanded"
      >
        <span class="thinking-chevron" :class="{ expanded: thinkingExpanded }">&#9654;</span>
        <span class="thinking-label">
          {{ thinkingExpanded ? '收起思考过程' : '查看思考过程' }}
        </span>
        <span v-if="message.thinkingTimeMs > 0" class="thinking-time">
          {{ formatThinkingTime(message.thinkingTimeMs) }}
        </span>
      </button>
      <div v-if="thinkingExpanded" class="thinking-body">
        {{ message.thinking }}
      </div>
    </div>

    <!-- Phase status indicator (shown during streaming before content arrives) -->
    <div v-if="isStreaming && phaseMessage && message.blocks.length === 0" class="phase-indicator">
      <span class="phase-spinner"></span>
      <span class="phase-text">{{ phaseMessage }}</span>
      <span class="phase-timer">{{ phaseElapsed }}s</span>
    </div>

    <!-- Content blocks -->
    <div
      class="content-blocks"
      @click="onContentClick"
      @mouseenter.capture="onContentMouseEnter"
      @mouseleave.capture="onContentMouseLeave"
    >
      <!-- Streaming text preview (shown before structured blocks arrive) -->
      <div v-if="message.streamingText" class="streaming-content" v-html="renderStreaming(message.streamingText)"></div>

      <template v-for="(block, index) in message.blocks" :key="index">
        <!-- Paragraph -->
        <p v-if="block.type === 'paragraph'" class="block-paragraph" v-html="renderCitations(block.text)"></p>

        <!-- Heading -->
        <h2 v-else-if="block.type === 'heading' && block.level === 2" class="block-heading" v-html="renderInline(block.text)"></h2>
        <h3 v-else-if="block.type === 'heading'" class="block-heading block-heading--h3" v-html="renderInline(block.text)"></h3>

        <!-- Code block -->
        <div v-else-if="block.type === 'code'" class="block-code-wrapper">
          <div class="code-header">
            <span v-if="block.language" class="code-lang">{{ block.language }}</span>
            <button class="code-copy-btn" type="button" @click="copyCode(block.code ?? block.text ?? '', $event)">复制</button>
          </div>
          <pre class="block-code"><code>{{ block.code ?? block.text }}</code></pre>
        </div>

        <!-- Unordered list -->
        <ul v-else-if="block.type === 'list' && !block.ordered" class="block-list">
          <li v-for="(item, idx) in block.items" :key="idx" v-html="renderInline(item)"></li>
        </ul>

        <!-- Ordered list -->
        <ol v-else-if="block.type === 'list' && block.ordered" class="block-list block-list--ordered">
          <li v-for="(item, idx) in block.items" :key="idx" v-html="renderInline(item)"></li>
        </ol>

        <!-- Table -->
        <div v-else-if="block.type === 'table' && block.headers" class="block-table-wrapper">
          <table class="block-table">
            <thead>
              <tr>
                <th v-for="(h, hi) in block.headers" :key="hi">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in block.rows" :key="ri">
                <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Divider -->
        <hr v-else-if="block.type === 'divider'" class="block-divider" />

        <!-- Blockquote -->
        <blockquote v-else-if="block.type === 'blockquote'" class="block-blockquote">
          {{ block.text }}
        </blockquote>

        <!-- Fallback: render as paragraph -->
        <p v-else-if="block.text" class="block-paragraph" v-html="renderCitations(block.text)"></p>
      </template>

      <!-- Streaming cursor -->
      <span v-if="isStreaming" class="streaming-cursor" aria-hidden="true"></span>
    </div>

    <!-- Source citation badges -->
    <div v-if="numberedSources.length > 0" class="sources-section">
      <span class="sources-label">引用来源</span>
      <div class="sources-badges">
        <button
          v-for="{ source, num } in numberedSources"
          :key="source.id"
          class="source-badge"
          :aria-label="'引用来源 ' + source.title"
          @mouseenter="emit('citation-hover', source.id, $event)"
          @mouseleave="emit('citation-leave')"
          @click="emit('citation-click', source.id)"
        >
          <span class="source-num">[{{ num }}]</span>
          {{ source.title }}
          <span v-if="source.page != null" class="source-page">p.{{ source.page }}</span>
        </button>
      </div>
    </div>

    <!-- AI message action bar -->
    <div class="message-actions">
      <button class="action-item" type="button" @click="handleCopy">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="4.5" y="4.5" width="8" height="8" rx="1.5"/><path d="M9.5 4.5V3a1.5 1.5 0 0 0-1.5-1.5H3A1.5 1.5 0 0 0 1.5 3v5A1.5 1.5 0 0 0 3 9.5h1.5"/></svg>
        <span>{{ copyLabel }}</span>
      </button>
      <button class="action-item" type="button" @click="emit('regenerate', message.id)">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M1.5 7a5.5 5.5 0 0 1 9.3-3.95M12.5 7a5.5 5.5 0 0 1-9.3 3.95"/><path d="M10.5 1v2.5H13"/><path d="M3.5 13v-2.5H1"/></svg>
        <span>重新生成</span>
      </button>
      <button v-if="isStreaming" class="action-item" type="button" @click="emit('stop')">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><rect x="2" y="2" width="10" height="10" rx="1.5"/></svg>
        <span>停止</span>
      </button>
      <template v-if="!isStreaming">
        <button class="action-item" type="button" @click="handleFollowUp">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M2 7h10M9 4l3 3-3 3"/></svg>
          <span>追问</span>
        </button>
        <button class="action-item action-item--danger" type="button" @click="emit('delete', message.id)">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M2 3.5h10"/><path d="M5.5 3.5V2.5a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1"/><path d="M3 3.5l.5 8a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1l.5-8"/></svg>
          <span>删除</span>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import type { AssistantMessage } from '../types/message'
import { renderInline, renderStreaming, renderParagraphWithCitations } from '../utils/citation-renderer'

const props = defineProps<{
  message: AssistantMessage
  isStreaming: boolean
  phaseMessage?: string
}>()

const emit = defineEmits<{
  (e: 'citation-hover', sourceId: string, event: MouseEvent): void
  (e: 'citation-leave'): void
  (e: 'citation-click', sourceId: string): void
  (e: 'regenerate', messageId: string): void
  (e: 'stop'): void
  (e: 'delete', messageId: string): void
  (e: 'follow-up', text: string): void
}>()

const thinkingExpanded = ref(false)
const copyLabel = ref('复制')

// Phase timer
const phaseElapsed = ref(0)
let phaseTimer: ReturnType<typeof setInterval> | null = null

watch(() => props.phaseMessage, (msg) => {
  if (msg) {
    phaseElapsed.value = 0
    if (phaseTimer) clearInterval(phaseTimer)
    phaseTimer = setInterval(() => { phaseElapsed.value += 1 }, 1000)
  } else {
    if (phaseTimer) { clearInterval(phaseTimer); phaseTimer = null }
  }
})

onBeforeUnmount(() => {
  if (phaseTimer) { clearInterval(phaseTimer); phaseTimer = null }
})

/** Deduplicated sources keyed by paper_id (or id as fallback), numbered [1], [2], … */
const numberedSources = computed(() => {
  const seen = new Map<string, { source: AssistantMessage['sources'][number]; num: number }>()
  let num = 0
  for (const s of props.message.sources) {
    const key = s.paper_id ?? s.id
    if (!seen.has(key)) {
      num += 1
      seen.set(key, { source: s, num })
    }
  }
  return [...seen.values()]
})

function formatThinkingTime(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remaining = seconds % 60
  return `${minutes}m${remaining}s`
}

/** Render paragraph with citation markers (delegates to utility) */
function renderCitations(text: string | undefined): string {
  return renderParagraphWithCitations(text, numberedSources.value)
}

/** Copy code block content to clipboard */
async function copyCode(text: string, event: Event) {
  await navigator.clipboard.writeText(text)
  const btn = (event.target as HTMLElement)
  btn.textContent = '已复制'
  setTimeout(() => { btn.textContent = '复制' }, 2000)
}

/** Copy AI message text to clipboard */
async function handleCopy() {
  const text = props.message.blocks
    .map((b) => b.text ?? (b.items ? b.items.join('\n') : ''))
    .filter(Boolean)
    .join('\n\n')
  await navigator.clipboard.writeText(text)
  copyLabel.value = '已复制'
  setTimeout(() => { copyLabel.value = '复制' }, 2000)
}

/** Summarize AI response and emit for follow-up */
function handleFollowUp() {
  const firstParagraph = props.message.blocks.find((b) => b.type === 'paragraph' && b.text)
  const summary = firstParagraph?.text?.slice(0, 100) ?? ''
  emit('follow-up', summary)
}

/** Handle clicks on inline citation markers via event delegation */
function onContentClick(event: MouseEvent): void {
  const target = (event.target as HTMLElement).closest('.cite-marker')
  if (!target) return
  const sourceId = (target as HTMLElement).dataset.sourceId
  if (sourceId) {
    event.preventDefault()
    emit('citation-click', sourceId)
  }
}

/** Handle hover on inline citation markers */
function onContentMouseEnter(event: MouseEvent): void {
  const target = (event.target as HTMLElement).closest('.cite-marker')
  if (!target) return
  const sourceId = (target as HTMLElement).dataset.sourceId
  if (sourceId) {
    emit('citation-hover', sourceId, event)
  }
}

function onContentMouseLeave(event: MouseEvent): void {
  const target = (event.target as HTMLElement).closest('.cite-marker')
  if (target) {
    emit('citation-leave')
  }
}
</script>

<style scoped>
.ai-message {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: var(--space-3) 0;
  padding: var(--space-4);
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  max-width: 88%;
  align-self: flex-start;
}

/* ── Thinking section ── */

.thinking-section {
  border-bottom: 1px solid var(--color-border-subtle);
  padding-bottom: var(--space-3);
}

.thinking-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  padding: var(--space-1) 0;
  cursor: pointer;
  background: none;
  border: none;
  transition: color 0.2s;
}

.thinking-toggle:hover {
  color: var(--color-accent);
}

.thinking-chevron {
  display: inline-block;
  font-size: 10px;
  transition: transform 0.2s ease;
}

.thinking-chevron.expanded {
  transform: rotate(90deg);
}

.thinking-label {
  user-select: none;
}

.thinking-time {
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

.thinking-body {
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
}

/* ── Content blocks ── */

/* ── Phase indicator ── */

.phase-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-accent-soft);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--color-accent);
}

.phase-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--color-accent-soft);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: phase-spin 0.8s linear infinite;
}

@keyframes phase-spin {
  to { transform: rotate(360deg); }
}

.phase-text {
  flex: 1;
}

.phase-timer {
  font-variant-numeric: tabular-nums;
  opacity: 0.6;
  font-size: 12px;
}

.content-blocks {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  font-size: var(--font-size-base);
  line-height: 1.7;
  color: var(--color-text-primary);
}

/* Streaming content uses the same block styles */
.streaming-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  font-size: var(--font-size-base);
  line-height: 1.7;
  color: var(--color-text-primary);
}

.streaming-content .block-paragraph {
  word-break: break-word;
}

.streaming-content .block-heading {
  font-weight: 600;
  color: var(--color-text-primary);
  margin-top: var(--space-2);
}

.streaming-content .block-list {
  padding-left: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.streaming-content .block-list--ordered {
  list-style: decimal;
}

.streaming-content .block-list li {
  word-break: break-word;
}

.streaming-content .block-list li::marker {
  color: var(--color-text-muted);
}

.streaming-content .block-blockquote {
  padding: var(--space-2) var(--space-4);
  border-left: 3px solid var(--color-accent);
  background: var(--color-accent-soft);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--color-text-secondary);
  font-style: italic;
  word-break: break-word;
}

.streaming-content .block-code {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  overflow-x: auto;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  color: var(--color-text-primary);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-sm);
}

.streaming-content .block-code code {
  font-family: inherit;
}

.block-paragraph {
  word-break: break-word;
}

.block-heading {
  font-weight: 600;
  color: var(--color-text-primary);
  margin-top: var(--space-2);
}

.block-heading--h3 {
  font-size: var(--font-size-lg);
  font-weight: 500;
}

/* Code block */
.block-code-wrapper {
  position: relative;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-subtle);
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-1) var(--space-2);
  background: var(--color-border-subtle);
}

.code-header .code-lang {
  position: static;
  background: none;
  border-radius: 0;
  padding: 0;
  font-size: 11px;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  line-height: 1;
}

.code-copy-btn {
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.code-copy-btn:hover {
  color: var(--color-accent);
  background: var(--color-accent-soft);
}

.block-code {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  overflow-x: auto;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  color: var(--color-text-primary);
}

.block-code code {
  font-family: inherit;
}

/* List */
.block-list {
  padding-left: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.block-list li {
  word-break: break-word;
}

.block-list li::marker {
  color: var(--color-text-muted);
}

/* Blockquote */
.block-blockquote {
  padding: var(--space-2) var(--space-4);
  border-left: 3px solid var(--color-accent);
  background: var(--color-accent-soft);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--color-text-secondary);
  font-style: italic;
  word-break: break-word;
}

/* Ordered list */
.block-list--ordered {
  padding-left: var(--space-5);
  list-style: decimal;
}

.block-list--ordered li::marker {
  color: var(--color-text-muted);
}

/* Table */
.block-table-wrapper {
  overflow-x: auto;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-subtle);
}

.block-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}

.block-table th,
.block-table td {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--color-border-subtle);
  text-align: left;
}

.block-table th {
  background: var(--color-surface-muted);
  font-weight: 600;
  white-space: nowrap;
}

.block-table td {
  word-break: break-word;
}

/* Divider */
.block-divider {
  border: none;
  border-top: 1px solid var(--color-border-subtle);
  margin: var(--space-2) 0;
}

/* ── Inline elements (from markdown-inline renderer) ── */

:deep(.inline-code) {
  font-family: var(--font-family-mono);
  font-size: 0.9em;
  padding: 1px 5px;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-subtle);
  border-radius: 3px;
  color: var(--color-accent);
}

/* ── Streaming cursor ── */

.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1.1em;
  background: var(--color-accent);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ── Source citations ── */

.sources-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border-subtle);
}

.sources-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.message-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border-subtle);
  flex-wrap: wrap;
}

.action-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.action-item:hover {
  color: var(--color-accent);
  background: var(--color-accent-soft);
}

.action-item--danger:hover {
  color: var(--color-error, #c53030);
  background: color-mix(in srgb, var(--color-error, #c53030) 10%, transparent);
}

.sources-badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.source-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--color-accent-soft);
  color: var(--color-accent);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  line-height: 1.4;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-badge:hover {
  border-color: var(--color-accent);
  background: var(--color-surface-muted);
}

.source-page {
  font-variant-numeric: tabular-nums;
  opacity: 0.75;
}

.source-num {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  margin-right: 2px;
}

/* ── Inline citation markers ── */

:deep(.cite-marker) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: super;
  font-size: 0.65em;
  font-weight: 600;
  line-height: 1;
  min-width: 1.5em;
  height: 1.5em;
  padding: 0 0.3em;
  margin-left: 1px;
  margin-right: 1px;
  color: var(--color-accent);
  background: var(--color-accent-soft);
  border: 1px solid transparent;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, transform 0.15s;
}

:deep(.cite-marker:hover) {
  background: var(--color-accent);
  color: #fff;
  transform: scale(1.1);
}

@media (max-width: 420px) {
  .ai-message {
    max-width: 100%;
    padding: var(--space-3);
  }
}
</style>
