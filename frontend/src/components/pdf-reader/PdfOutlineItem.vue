<template>
  <li role="treeitem" :style="{ paddingLeft: depth * 16 + 'px' }">
    <button
      class="outline-item-btn"
      :class="{ 'outline-item-btn--active': isActive }"
      @click="emit('navigate', item.pageNumber ?? 1)"
    >
      {{ item.title }}
    </button>
    <ul v-if="item.items.length > 0" role="group">
      <PdfOutlineItem
        v-for="(child, index) in item.items"
        :key="index"
        :item="child"
        :depth="depth + 1"
        :current-page="currentPage"
        @navigate="(p: number) => emit('navigate', p)"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { OutlineItem } from './PdfOutline.vue'

const props = defineProps<{
  item: OutlineItem
  depth: number
  currentPage: number
}>()

const emit = defineEmits<{
  (e: 'navigate', pageNumber: number): void
}>()

const isActive = computed(() => {
  if (!props.item.pageNumber) return false
  return props.item.pageNumber === props.currentPage
})
</script>

<style scoped>
ul {
  list-style: none;
}

.outline-item-btn {
  display: block;
  width: 100%;
  text-align: left;
  padding: 6px 12px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.outline-item-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.outline-item-btn--active {
  color: var(--color-accent);
  background: var(--color-accent-soft);
  font-weight: 500;
}
</style>
