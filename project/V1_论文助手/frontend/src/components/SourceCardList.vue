<template>
  <div class="source-list">
    <div class="source-header">
      <span>参考来源</span>
      <span class="source-count">{{ sources.length }}</span>
    </div>
    <div class="source-cards">
      <div v-for="(source, index) in sources" :key="source.id" class="source-card" @click="openSource(source)">
        <div class="source-badge">{{ index + 1 }}</div>
        <div class="source-content">
          <div class="source-title">{{ source.title || '未知文档' }}</div>
          <div class="source-meta">
            <span v-if="source.page" class="source-page">第 {{ source.page }} 页</span>
            <span v-if="source.section" class="source-section">{{ source.section }}</span>
          </div>
          <div v-if="source.content" class="source-content-preview">{{ truncateContent(source.content) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface SourceCard {
  id: string
  paper_id?: string
  title: string
  page?: number
  section?: string
  file_path?: string
  content?: string
}

defineProps<{
  sources: SourceCard[]
}>()

function truncateContent(content: string, maxLength = 150) {
  if (content.length <= maxLength) return content
  return content.slice(0, maxLength) + '...'
}

function openSource(source: SourceCard) {
  // 优先通过后端 API 打开 PDF（从备份目录）
  if (source.paper_id) {
    const apiUrl = `http://127.0.0.1:8000/api/v1/papers/${source.paper_id}/open`
    openPdf(apiUrl, source.page || 1)
    return
  }

  // 降级：直接使用文件路径
  if (source.file_path) {
    openPdf(source.file_path, source.page || 1)
  }
}

function openPdf(url: string, _page: number) {
  // WPS 插件环境：使用 WPS JS API
  // @ts-ignore WPS 全局对象
  const wps = globalThis.wps || globalThis.Window?.wps
  if (wps) {
    try {
      // WPS JS API 打开文档
      wps.WpsApplication().Documents.Open(url)
      return
    } catch {
      // WPS API 失败，降级
    }
  }

  // 浏览器降级：新标签页打开
  window.open(url, '_blank')
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
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-card);
  border: 1px solid var(--color-source-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.source-card:hover {
  border-color: var(--color-source-hover);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

.source-badge {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent);
  color: white;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
}

.source-content {
  flex: 1;
  min-width: 0;
}

.source-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}

.source-meta {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.source-page,
.source-section {
  font-size: 11px;
  color: var(--color-text-muted);
}

.source-content-preview {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin-top: var(--space-1);
}
</style>
