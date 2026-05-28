<template>
  <Transition name="outline-sidebar">
    <div
      v-if="open"
      class="outline-sidebar"
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
          @navigate="(p: number) => emit('navigate', p)"
        />
      </ul>
    </div>
  </Transition>
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
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'navigate', pageNumber: number): void
}>()
</script>

<style scoped>
.outline-sidebar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 220px;
  background: var(--color-surface-card);
  border-right: 1px solid var(--color-border-subtle);
  display: flex;
  flex-direction: column;
  z-index: 10;
  overflow: hidden;
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

.outline-sidebar-enter-active {
  transition: transform 250ms var(--ease-out-expo);
}
.outline-sidebar-leave-active {
  transition: transform 200ms ease-in-out;
}
.outline-sidebar-enter-from,
.outline-sidebar-leave-to {
  transform: translateX(-100%);
}

@media (max-width: 800px) {
  .outline-sidebar {
    position: fixed;
    z-index: 220;
    box-shadow: var(--shadow-drawer);
  }
}

@media (max-width: 420px) {
  .outline-sidebar {
    width: 100%;
  }
}
</style>
