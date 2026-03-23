<script setup lang="ts">
import { useMockStore } from '../../stores/mockStore'

const store = useMockStore()

const tabs = [
  { id: 'ingest' as const, label: '导入' },
  { id: 'chat' as const, label: '对话' },
  { id: 'settings' as const, label: '设置' }
]
</script>

<template>
  <div class="tab-bar">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      :class="['tab-btn', { active: store.activeTab === tab.id }]"
      @click="store.setActiveTab(tab.id)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<style scoped>
.tab-bar {
  display: flex;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  flex: 1;
  padding: 12px 16px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  color: var(--text-primary);
  background: var(--bg-main);
  border-bottom: 2px solid var(--primary);
}
</style>
