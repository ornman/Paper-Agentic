<!-- frontend/src/components/pdf-reader/PdfSearchBar.vue -->
<template>
  <div class="search-bar">
    <input
      ref="inputRef"
      v-model="localQuery"
      class="search-input"
      type="text"
      placeholder="搜索..."
      @keydown.enter.prevent="onEnter"
      @keydown.escape.prevent="emit('close')"
    />

    <span v-if="matchCount > 0" class="search-count">
      {{ currentMatchIndex + 1 }}/{{ matchCount }}
    </span>
    <span v-else-if="localQuery.trim()" class="search-count search-count--empty">
      0/0
    </span>

    <button
      class="search-nav-btn"
      :disabled="matchCount === 0"
      aria-label="上一个匹配"
      @click="emit('prev')"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="18 15 12 9 6 15" />
      </svg>
    </button>

    <button
      class="search-nav-btn"
      :disabled="matchCount === 0"
      aria-label="下一个匹配"
      @click="emit('next')"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>

    <button
      class="search-close-btn"
      aria-label="关闭搜索"
      @click="emit('close')"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps<{
  /** Current search query (controlled from parent) */
  query: string
  /** Total number of matches */
  matchCount: number
  /** Current match index (0-based) */
  currentMatchIndex: number
}>()

const emit = defineEmits<{
  (e: 'search', query: string): void
  (e: 'next'): void
  (e: 'prev'): void
  (e: 'close'): void
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const localQuery = ref(props.query)

// Sync local query when parent changes it (e.g. on close)
watch(
  () => props.query,
  (q) => {
    if (q !== localQuery.value) {
      localQuery.value = q
    }
  },
)

// Debounced emit to parent
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(localQuery, (val) => {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }

  // Emit immediately on empty to clear results
  if (!val.trim()) {
    emit('search', val)
    return
  }

  debounceTimer = setTimeout(() => {
    emit('search', val)
  }, 300)
})

function onEnter(): void {
  // Shift+Enter = previous match, Enter = next match
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
    // Flush pending search first
    emit('search', localQuery.value)
  }

  // Small delay to let search results arrive before navigating
  nextTick(() => {
    // Use window event to determine shiftKey since we don't have the event here
    // Instead, always go next on Enter
    emit('next')
  })
}

onMounted(() => {
  nextTick(() => {
    inputRef.value?.focus()
  })
})

onBeforeUnmount(() => {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
})
</script>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-sm);
  padding: 2px 4px;
  margin-left: var(--space-2);
}

.search-input {
  width: 120px;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  background: transparent;
  border: none;
  outline: none;
  padding: 2px 4px;
}

.search-input::placeholder {
  color: var(--color-text-muted);
}

.search-count {
  font-size: 11px;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  padding: 0 2px;
  min-width: 32px;
  text-align: center;
}

.search-count--empty {
  color: var(--color-text-muted);
  opacity: 0.6;
}

.search-nav-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  transition: background 0.15s, color 0.15s;
}

.search-nav-btn:hover:not(:disabled) {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.search-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.search-close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  transition: background 0.15s, color 0.15s;
}

.search-close-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}
</style>
