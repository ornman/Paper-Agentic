<template>
  <div class="source-list">
    <div class="source-header">
      <span>参考来源</span>
      <span class="source-count">{{ sources.length }}</span>
    </div>
    <div class="source-cards">
      <div v-for="source in sources" :key="source.id" class="source-card">
        <div class="source-title">{{ source.title || '未知文档' }}</div>
        <div v-if="source.page" class="source-page">第 {{ source.page }} 页</div>
        <div v-if="source.snippet" class="source-snippet">{{ truncateSnippet(source.snippet) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface SourceCard {
  id: string
  title: string
  page?: number
  snippet: string
}

defineProps<{
  sources: SourceCard[]
}>()

function truncateSnippet(snippet: string, maxLength = 120) {
  if (snippet.length <= maxLength) return snippet
  return snippet.slice(0, maxLength) + '...'
}
</script>

<style scoped>
.source-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-source-bg);
  border: 1px solid var(--color-source-border);
  border-radius: var(--radius-sm);
}

.source-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.source-count {
  margin-left: auto;
  padding: 2px 8px;
  background: var(--color-surface-base);
  color: var(--color-text-secondary);
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
}

.source-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.source-card {
  padding: var(--space-3);
  background: var(--color-surface-card);
  border: 1px solid var(--color-source-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.source-card:hover {
  border-color: var(--color-source-hover);
}

.source-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}

.source-page {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-bottom: var(--space-1);
}

.source-snippet {
  font-size: var(--font-size-caption);
  color: var(--color-text-secondary);
  line-height: 1.6;
}
</style>
