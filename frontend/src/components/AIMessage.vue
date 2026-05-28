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

    <!-- Content blocks -->
    <div class="content-blocks">
      <template v-for="(block, index) in message.blocks" :key="index">
        <!-- Paragraph -->
        <p v-if="block.type === 'paragraph'" class="block-paragraph">
          {{ block.text }}
        </p>

        <!-- Heading -->
        <h2 v-else-if="block.type === 'heading' && block.level === 2" class="block-heading">
          {{ block.text }}
        </h2>
        <h3 v-else-if="block.type === 'heading'" class="block-heading block-heading--h3">
          {{ block.text }}
        </h3>

        <!-- Code block -->
        <div v-else-if="block.type === 'code'" class="block-code-wrapper">
          <div v-if="block.language" class="code-lang">{{ block.language }}</div>
          <pre class="block-code"><code>{{ block.text }}</code></pre>
        </div>

        <!-- List -->
        <ul v-else-if="block.type === 'list'" class="block-list">
          <li v-for="(item, idx) in block.items" :key="idx">{{ item }}</li>
        </ul>

        <!-- Blockquote -->
        <blockquote v-else-if="block.type === 'blockquote'" class="block-blockquote">
          {{ block.text }}
        </blockquote>

        <!-- Fallback: render as paragraph -->
        <p v-else-if="block.text" class="block-paragraph">
          {{ block.text }}
        </p>
      </template>

      <!-- Streaming cursor -->
      <span v-if="isStreaming" class="streaming-cursor" aria-hidden="true"></span>
    </div>

    <!-- Source citation badges -->
    <div v-if="message.sources.length > 0" class="sources-section">
      <span class="sources-label">引用来源</span>
      <div class="sources-badges">
        <button
          v-for="source in message.sources"
          :key="source.id"
          class="source-badge"
          @mouseenter="emit('citation-hover', source.id, $event)"
          @mouseleave="emit('citation-leave')"
          @click="emit('citation-click', source.id)"
        >
          {{ source.title }}
          <span v-if="source.page != null" class="source-page">p.{{ source.page }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { AssistantMessage } from '../stores/conversation'

defineProps<{
  message: AssistantMessage
  isStreaming: boolean
}>()

const emit = defineEmits<{
  (e: 'citation-hover', sourceId: string, event: MouseEvent): void
  (e: 'citation-leave'): void
  (e: 'citation-click', sourceId: string): void
}>()

const thinkingExpanded = ref(false)

function formatThinkingTime(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remaining = seconds % 60
  return `${minutes}m${remaining}s`
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

.content-blocks {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  font-size: var(--font-size-base);
  line-height: 1.7;
  color: var(--color-text-primary);
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

.code-lang {
  position: absolute;
  top: 0;
  right: 0;
  padding: var(--space-1) var(--space-2);
  font-size: 11px;
  color: var(--color-text-muted);
  background: var(--color-border-subtle);
  border-bottom-left-radius: var(--radius-sm);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  line-height: 1;
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
  max-width: 220px;
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
</style>
