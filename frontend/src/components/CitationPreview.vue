<template>
  <Teleport to="body">
    <Transition name="preview-fade">
      <div
        v-if="visible && source"
        class="citation-preview"
        :style="{ left: clampedPos.left + 'px', top: clampedPos.top + 'px' }"
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
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SourceCard } from '../types/source'

const TOOLTIP_WIDTH = 360
const TOOLTIP_HEIGHT = 200
const MARGIN = 16
const OFFSET = 12

const props = defineProps<{
  visible: boolean
  source: SourceCard | null
  x: number
  y: number
}>()

const emit = defineEmits<{
  (e: 'preview-enter'): void
  (e: 'preview-leave'): void
}>()

const clampedPos = computed(() => {
  let left = props.x + OFFSET
  let top = props.y + OFFSET

  const maxX = window.innerWidth - TOOLTIP_WIDTH - MARGIN
  const maxY = window.innerHeight - TOOLTIP_HEIGHT - MARGIN

  left = Math.min(left, maxX)
  top = Math.min(top, maxY)
  left = Math.max(left, MARGIN)
  top = Math.max(top, MARGIN)

  return { left, top }
})
</script>

<style scoped>
.citation-preview {
  position: fixed;
  z-index: 200;
  max-width: 360px;
  padding: var(--space-3) var(--space-4);
  background: color-mix(in srgb, var(--color-surface-card) 88%, transparent);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08), 0 1px 4px rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(12px) saturate(1.2);
  -webkit-backdrop-filter: blur(12px) saturate(1.2);
}

.preview-fade-enter-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.preview-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.preview-fade-enter-from {
  opacity: 0;
  transform: scale(0.95);
}
.preview-fade-leave-to {
  opacity: 0;
  transform: scale(0.97);
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
