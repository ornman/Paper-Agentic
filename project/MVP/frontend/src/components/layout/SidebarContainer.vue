<script setup lang="ts">
import TopNavBar from './TopNavBar.vue'
import KnowledgeBar from './KnowledgeBar.vue'
import BottomActionBar from './BottomActionBar.vue'
import EmptyState from '../conversation/EmptyState.vue'
import HistoryDrawer from '../overlays/HistoryDrawer.vue'

// Task 2 只负责把右侧侧边栏布局骨架搭起来。
// 这里故意不用 store，也不接真实宿主状态，避免提前进入 Task 3+。
const sidebarWidth = '380'
const historyDrawerOpen = false
</script>

<template>
  <aside
    class="sidebar-container"
    data-testid="sidebar-container"
    :data-sidebar-width="sidebarWidth"
    aria-label="WPS 论文创作辅助侧边栏"
  >
    <div class="sidebar-chrome" data-testid="sidebar-chrome">
      <TopNavBar />
      <KnowledgeBar />
    </div>

    <!-- 内容区当前只挂空态，后续任务再替换成真实消息流。 -->
    <main class="sidebar-main" data-testid="sidebar-main">
      <div class="sidebar-content" data-testid="content-area">
        <EmptyState />
      </div>
    </main>

    <BottomActionBar />

    <!-- 历史抽屉先保留壳体，默认关闭，不接真实历史数据。 -->
    <HistoryDrawer :open="historyDrawerOpen" />
  </aside>
</template>

<style scoped>
.sidebar-container {
  --sidebar-width: 380px;

  position: relative;
  display: grid;
  grid-template-rows: auto 1fr auto;
  width: min(100%, var(--sidebar-width));
  min-height: 100vh;
  margin-left: auto;
  padding: 12px;
  background: linear-gradient(180deg, #f8f9fb 0%, #f3f5f8 100%);
  border-left: 1px solid var(--color-border-subtle);
  color: var(--color-text-primary);
  overflow: hidden;
}

.sidebar-chrome {
  display: grid;
  gap: 10px;
  padding: 4px 4px 12px;
  border-bottom: 1px solid rgba(17, 24, 39, 0.06);
}

.sidebar-main {
  min-height: 0;
  padding-top: 12px;
}

.sidebar-content {
  height: 100%;
  padding: 0 4px 4px;
  overflow-y: auto;
}
</style>
