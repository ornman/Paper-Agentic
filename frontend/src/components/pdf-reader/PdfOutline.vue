<template>
  <div
    class="outline-wrapper"
    :class="{ 'outline-wrapper--open': open }"
    role="navigation"
    aria-label="PDF 目录"
  >
    <div class="outline-header">
      <span class="outline-title">目录</span>
      <button
        class="outline-close-btn"
        aria-label="关闭目录"
        @click="emit('close')"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>

    <div v-if="items.length === 0" class="outline-empty">
      此文档无目录
    </div>

    <ul v-else class="outline-list" role="tree">
      <PdfOutlineItem
        v-for="(item, index) in items"
        :key="index"
        :item="item"
        :depth="0"
        :current-page="currentPage"
        @navigate="(p: number) => emit('navigate', p)"
      />
    </ul>
  </div>
</template>

<script setup lang="ts">
import PdfOutlineItem from './PdfOutlineItem.vue'

export interface OutlineItem {
  title: string
  dest: unknown
  items: OutlineItem[]
  pageNumber?: number
}

defineProps<{
  open: boolean
  items: OutlineItem[]
  currentPage: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'navigate', pageNumber: number): void
}>()
</script>

<style scoped>
.outline-wrapper {
  width: 0;
  overflow: hidden;
  background: var(--color-surface-card);
  border-right: 1px solid transparent;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 250ms var(--ease-out-expo, cubic-bezier(0.16, 1, 0.3, 1)),
              border-color 250ms ease;
}

.outline-wrapper--open {
  width: 240px;
  border-right-color: var(--color-border-subtle);
}

.outline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.outline-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.outline-close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  transition: background 0.15s;
}

.outline-close-btn:hover {
  background: var(--color-surface-muted);
}

.outline-empty {
  padding: var(--space-4);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  text-align: center;
}

.outline-list {
  list-style: none;
  overflow-y: auto;
  flex: 1;
  padding: var(--space-2) 0;
}

@media (max-width: 800px) {
  .outline-wrapper {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 220;
    box-shadow: var(--shadow-drawer);
  }
  .outline-wrapper--open {
    width: 260px;
  }
}

@media (max-width: 420px) {
  .outline-wrapper--open {
    width: 100%;
  }
}
</style>
