<template>
  <div class="source-panel">
    <div class="source-panel-title">引用来源</div>
    <div class="source-list">
      <button
        v-for="source in sources"
        :key="source.id"
        class="source-card"
        type="button"
        @click="emit('open-source', source)"
      >
        <span class="source-card-title">{{ source.title }}</span>
        <span v-if="source.page" class="source-card-page">第 {{ source.page }} 页</span>
        <span v-if="source.section" class="source-card-section">{{ source.section }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SourceCard } from '../types/source'

defineProps<{
  sources: SourceCard[]
}>()

const emit = defineEmits<{
  (e: 'open-source', source: SourceCard): void
}>()
</script>

<style scoped>
.source-panel {
  border-top: 1px solid var(--color-border-subtle);
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface-card);
}

.source-panel-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.source-list {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
}

.source-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: var(--color-surface-base);
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
  transition: border-color 0.15s ease;
}

.source-card:hover {
  border-color: var(--color-accent);
}

.source-card-title {
  font-size: 13px;
  color: var(--color-text-primary);
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-card-page,
.source-card-section {
  font-size: 11px;
  color: var(--color-text-muted);
}
</style>
