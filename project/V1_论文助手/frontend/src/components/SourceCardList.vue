<template>
  <div class="source-list">
    <button
      v-for="(source, index) in sources"
      :key="source.id"
      class="source-card"
      :class="{ 'source-card--active': source.id === activeSourceId }"
      type="button"
      @click="emit('open-source', source)"
    >
      <div class="source-badge">{{ index + 1 }}</div>
      <div class="source-content">
        <div class="source-title">{{ source.title || '未知文档' }}</div>
        <div class="source-meta">
          <span v-if="source.page" class="source-page">第 {{ source.page }} 页</span>
          <span v-if="source.section" class="source-section">{{ source.section }}</span>
        </div>
        <div v-if="source.content" class="source-preview">{{ source.content }}</div>
      </div>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { SourceCard } from '../types/source'

defineProps<{
  sources: SourceCard[]
  activeSourceId?: string
}>()

const emit = defineEmits<{
  (event: 'open-source', source: SourceCard): void
}>()
</script>

<style scoped>
.source-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.source-card {
  width: 100%;
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.source-card:hover {
  background: rgba(0, 0, 0, 0.025);
  border-color: rgba(59, 130, 246, 0.28);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.source-card--active {
  background: rgba(59, 130, 246, 0.05);
  border-color: rgba(59, 130, 246, 0.45);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.12);
}

.source-badge {
  flex-shrink: 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.6;
}

.source-content {
  flex: 1;
  min-width: 0;
}

.source-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.5;
}

.source-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
}

.source-page,
.source-section {
  font-size: 11px;
  color: var(--color-text-muted);
}

.source-preview {
  margin-top: 6px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
