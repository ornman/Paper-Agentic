<template>
  <Teleport to="body">
    <div
      v-if="visible && source"
      class="citation-preview"
      :style="{ left: x + 12 + 'px', top: y + 12 + 'px' }"
      @mouseenter="emit('preview-enter')"
      @mouseleave="emit('preview-leave')"
    >
      <div class="preview-title">{{ source.title }}</div>
      <div v-if="source.page || source.section" class="preview-meta">
        <span v-if="source.page">第 {{ source.page }} 页</span>
        <span v-if="source.section">{{ source.section }}</span>
      </div>
      <div v-if="source.content" class="preview-content">{{ source.content }}</div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { SourceCard } from '../types/source'

defineProps<{
  visible: boolean
  source: SourceCard | null
  x: number
  y: number
}>()

const emit = defineEmits<{
  (e: 'preview-enter'): void
  (e: 'preview-leave'): void
}>()
</script>

<style scoped>
.citation-preview {
  position: fixed;
  z-index: 200;
  max-width: 360px;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  animation: fadeIn 0.15s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.preview-meta {
  display: flex;
  gap: var(--space-2);
  font-size: 11px;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}

.preview-content {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
}
</style>
