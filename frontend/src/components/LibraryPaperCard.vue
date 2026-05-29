<template>
  <!-- Normal / successful paper card -->
  <label
    v-if="paper.status !== 'failed'"
    class="paper-card"
    :class="{ 'paper-card--selected': selected }"
  >
    <input
      type="checkbox"
      class="paper-card-checkbox"
      :checked="selected"
      @change="emit('toggle', paper.paper_id)"
    />
    <div class="paper-card-body">
      <span class="paper-card-title" v-html="highlightTitle" />
      <span class="paper-card-meta">
        {{ authorDisplay }}
        <template v-if="paper.year"> · {{ paper.year }}</template>
        · {{ paper.total_pages }} 页
        · {{ paper.chunk_count }} 个引用片段
      </span>
      <div v-if="displayKeywords.length" class="paper-card-keywords">
        <span v-for="kw in displayKeywords" :key="kw" class="paper-card-pill">{{ kw }}</span>
        <span v-if="paper.keywords.length > maxKeywords" class="paper-card-pill paper-card-pill--more">
          +{{ paper.keywords.length - maxKeywords }}
        </span>
      </div>
    </div>
    <div class="paper-card-actions">
      <button
        class="paper-card-action"
        type="button"
        title="找相似"
        @click.prevent.stop="emit('similar', paper.paper_id)"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      </button>
      <button
        class="paper-card-action paper-card-action--danger"
        type="button"
        title="移除"
        @click.prevent.stop="emit('remove', paper.paper_id)"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      </button>
    </div>
  </label>

  <!-- Failed import card -->
  <div v-else class="paper-card paper-card--failed">
    <div class="paper-card-body">
      <span class="paper-card-title" v-html="highlightTitle" />
      <span class="paper-card-failed-badge">导入失败</span>
      <span class="paper-card-meta">
        {{ authorDisplay }}
        <template v-if="paper.year"> · {{ paper.year }}</template>
      </span>
    </div>
    <div class="paper-card-actions">
      <button
        class="paper-card-action"
        type="button"
        title="重试"
        @click.prevent.stop="emit('retry', paper.file_path)"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
      </button>
      <button
        class="paper-card-action paper-card-action--danger"
        type="button"
        title="移除"
        @click.prevent.stop="emit('remove', paper.paper_id)"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PaperItem } from '../services/library-api'

const props = withDefaults(defineProps<{
  paper: PaperItem
  selected: boolean
  highlightFn?: (text: string) => string
  maxKeywords?: number
}>(), {
  maxKeywords: 3,
})

const emit = defineEmits<{
  (e: 'toggle', id: string): void
  (e: 'remove', id: string): void
  (e: 'similar', id: string): void
  (e: 'retry', filePath: string): void
}>()

const highlightTitle = computed(() =>
  props.highlightFn ? props.highlightFn(props.paper.title) : props.paper.title,
)

const displayKeywords = computed(() =>
  props.paper.keywords.slice(0, props.maxKeywords),
)

const authorDisplay = computed(() => {
  const authors = props.paper.authors
  if (!authors) return '未知作者'
  if (authors.length <= 28) return authors
  const first = authors.split(',')[0]?.trim() ?? authors
  return `${first} et al.`
})
</script>

<style scoped>
.paper-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.2s ease, box-shadow 0.2s ease;
}

.paper-card:hover {
  background: var(--color-surface-muted);
}

.paper-card--selected {
  background: var(--color-accent-soft);
  box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--color-accent) 25%, transparent);
}

.paper-card--selected:hover {
  background: var(--color-accent-soft);
}

.paper-card-checkbox {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  accent-color: var(--color-accent);
  cursor: pointer;
}

.paper-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.paper-card-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.paper-card-title :deep(mark) {
  background: color-mix(in srgb, var(--color-accent) 25%, transparent);
  color: inherit;
  border-radius: 2px;
  padding: 0 1px;
}

.paper-card-meta {
  font-size: 12px;
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.paper-card-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}

.paper-card-pill {
  display: inline-block;
  padding: 1px 6px;
  font-size: 11px;
  border-radius: 999px;
  background: var(--color-surface-muted);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.paper-card-pill--more {
  background: transparent;
  color: var(--color-text-muted);
}

.paper-card--failed {
  background: color-mix(in srgb, var(--color-error, #c53030) 5%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-error, #c53030) 15%, transparent);
  cursor: default;
}

.paper-card--failed .paper-card-title {
  opacity: 0.7;
}

.paper-card-failed-badge {
  display: inline-block;
  padding: 1px 6px;
  font-size: 11px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-error, #c53030) 15%, transparent);
  color: var(--color-error, #c53030);
  font-weight: 500;
}

.paper-card-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  transition: opacity var(--duration-fast) ease;
}

.paper-card:hover .paper-card-actions {
  opacity: 1;
}

.paper-card-action {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.paper-card-action:hover {
  color: var(--color-text-primary);
  background: var(--color-surface-muted);
}

.paper-card-action--danger:hover {
  color: var(--color-error);
}
</style>
