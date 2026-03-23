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
    <button class="new-session-btn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="12" y1="5" x2="12" y2="19"/>
        <line x1="5" y1="12" x2="19" y2="12"/>
      </svg>
      新会话
    </button>
  </div>
</template>

<style scoped>
.session-bar {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border);
}

.session-select {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.2s;
}

.session-select:focus {
  outline: none;
  border-color: var(--primary);
}

.new-session-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.new-session-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.new-session-btn svg {
  width: 16px;
  height: 16px;
}
</style>
