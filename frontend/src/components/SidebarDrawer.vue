<template>
  <Teleport to="body">
    <Transition name="sidebar-backdrop">
      <div
        v-if="visible"
        class="sidebar-backdrop"
        @click="emit('close')"
      />
    </Transition>

    <Transition name="sidebar-drawer">
      <div v-if="visible" class="sidebar-drawer" role="dialog" aria-modal="true" tabindex="-1" @click.stop @keydown.escape="emit('close')">
        <div class="sidebar-header">
          <div class="sidebar-tabs" role="tablist">
            <button
              role="tab"
              class="sidebar-tab"
              :class="{ 'sidebar-tab--active': activeTab === 'history' }"
              :aria-selected="activeTab === 'history'"
              @click="emit('update:activeTab', 'history')"
            >
              对话历史
            </button>
            <button
              role="tab"
              class="sidebar-tab"
              :class="{ 'sidebar-tab--active': activeTab === 'library' }"
              :aria-selected="activeTab === 'library'"
              @click="emit('update:activeTab', 'library')"
            >
              文献库
            </button>
            <span
              class="sidebar-tab-indicator"
              :class="{ 'sidebar-tab-indicator--right': activeTab === 'library' }"
            />
          </div>

          <button
            class="sidebar-close-btn"
            type="button"
            aria-label="关闭侧栏"
            @click="emit('close')"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div class="sidebar-body">
          <Transition name="fade" mode="out-in">
            <div :key="activeTab" class="tab-content" role="tabpanel">
              <slot :name="activeTab" />
            </div>
          </Transition>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
export type SidebarTab = 'history' | 'library'

defineProps<{
  visible: boolean
  activeTab: SidebarTab
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update:activeTab', tab: SidebarTab): void
}>()
</script>

<style scoped>
/* ─── Backdrop ─── */
.sidebar-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.sidebar-backdrop-enter-active {
  transition: opacity 300ms var(--ease-out-expo);
}

.sidebar-backdrop-leave-active {
  transition: opacity 250ms var(--ease-in-out);
}

.sidebar-backdrop-enter-from,
.sidebar-backdrop-leave-to {
  opacity: 0;
}

/* ─── Drawer ─── */
.sidebar-drawer {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 210;
  width: 320px;
  max-width: 80vw;
  display: flex;
  flex-direction: column;
  background: var(--color-surface-card);
  box-shadow: var(--shadow-drawer);
}

.sidebar-drawer-enter-active {
  transition: transform 300ms var(--ease-out-expo);
}

.sidebar-drawer-leave-active {
  transition: transform 250ms var(--ease-in-out);
}

.sidebar-drawer-enter-from,
.sidebar-drawer-leave-to {
  transform: translateX(-100%);
}

/* ─── Header ─── */
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-4) 0;
  flex-shrink: 0;
}

.sidebar-tabs {
  position: relative;
  display: flex;
  gap: var(--space-1);
  background: var(--color-surface-muted);
  border-radius: var(--radius-sm);
  padding: 3px;
}

.sidebar-tab {
  position: relative;
  z-index: 1;
  padding: var(--space-2) var(--space-4);
  border-radius: 6px;
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  background: transparent;
  transition: color var(--duration-normal) ease;
  white-space: nowrap;
}

.sidebar-tab--active {
  color: var(--color-text-primary);
}

.sidebar-tab:not(.sidebar-tab--active):hover {
  color: var(--color-text-primary);
}

/* ─── Tab indicator ─── */
.sidebar-tab-indicator {
  position: absolute;
  top: 3px;
  left: 3px;
  width: calc(50% - 3.5px);
  height: calc(100% - 6px);
  background: var(--color-surface-card);
  border-radius: 6px;
  box-shadow: var(--shadow-sm);
  transition: transform var(--duration-normal) var(--ease-out-expo);
  pointer-events: none;
}

.sidebar-tab-indicator--right {
  transform: translateX(100%);
}

/* ─── Close button ─── */
.sidebar-close-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  transition: background var(--duration-fast) ease, color var(--duration-fast) ease;
  flex-shrink: 0;
}

.sidebar-close-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

/* ─── Body ─── */
.sidebar-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-4);
}

@media (max-width: 420px) {
  .sidebar-drawer {
    width: 100%;
    max-width: 100%;
  }
}
</style>
