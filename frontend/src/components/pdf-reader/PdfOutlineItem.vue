<template>
  <li role="treeitem" :style="{ paddingLeft: depth * 16 + 'px' }">
    <button
      class="outline-item-btn"
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
        @navigate="(p: number) => emit('navigate', p)"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import type { OutlineItem } from './PdfOutline.vue'

defineProps<{
  item: OutlineItem
  depth: number
}>()

const emit = defineEmits<{
  (e: 'navigate', pageNumber: number): void
}>()
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
</style>
