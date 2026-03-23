<script setup lang="ts">
import { useMockStore } from '../../stores/mockStore'

const store = useMockStore()
</script>

<template>
  <div class="session-bar">
    <select
      :value="store.activeSessionId"
      @change="store.setActiveSession(($event.target as HTMLSelectElement).value)"
      class="session-select"
    >
      <option
        v-for="session in store.sessions"
        :key="session.id"
        :value="session.id"
      >
        {{ session.title }}
      </option>
    </select>
    <button class="new-session-btn">+ 新会话</button>
  </div>
</template>

<style scoped>
.session-bar {
  display: flex;
  gap: 12px;
  padding: 12px 20px;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border);
}

.session-select {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
}

.session-select:focus {
  outline: none;
  border-color: var(--primary);
}

.new-session-btn {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.new-session-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}
</style>
