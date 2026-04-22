<template>
  <div class="source-list">
    <div class="source-header">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
        <path d="M7 0C3.13 0 0 3.13 0 7s3.13 7 7 7 7-3.13 7-7-3.13-7-7-7zm0 12c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/>
        <path d="M6 4h2v5H6z"/>
        <circle cx="7" cy="11" r="1"/>
      </svg>
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
  gap: var(--claude-spacing-sm);
  padding: var(--claude-spacing-md);
  background: var(--claude-bg-main);
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
}

.source-header {
  display: flex;
  align-items: center;
  gap: var(--claude-spacing-xs);
  font-size: 12px;
  font-weight: 600;
  color: var(--claude-text-secondary);
}

.source-count {
  margin-left: auto;
  padding: 2px 8px;
  background: var(--claude-primary-light);
  color: var(--claude-primary);
  border-radius: var(--claude-radius-full);
  font-size: 11px;
  font-weight: 500;
}

.source-cards {
  display: flex;
  flex-direction: column;
  gap: var(--claude-spacing-sm);
}

.source-card {
  padding: 10px 12px;
  background: var(--claude-bg-card);
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-sm);
  cursor: pointer;
  transition: all 0.2s;
}

.source-card:hover {
  border-color: var(--claude-primary);
  box-shadow: var(--claude-shadow-sm);
}

.source-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--claude-text-primary);
  margin-bottom: var(--claude-spacing-xs);
}

.source-page {
  font-size: 11px;
  color: var(--claude-text-muted);
  margin-bottom: var(--claude-spacing-xs);
}

.source-snippet {
  font-size: 12px;
  color: var(--claude-text-secondary);
  line-height: 1.6;
}
</style>
