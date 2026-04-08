<script setup lang="ts">
import { getActivePinia } from 'pinia'
import { computed, onMounted } from 'vue'
import ImportPdfButton from '../library/ImportPdfButton.vue'
import { useLibraryStore } from '../../stores/library'

// KnowledgeBar 的职责不是“后台信息卡”，而是“价值证明条”。
//
// 第一性原理：用户打开侧边栏的第一秒，需要被快速回答两件事：
// 1) 这个插件能给我的论文写作带来什么确定性收益；
// 2) 当前知识库是否可用、规模如何。
//
// 因此这里保留原有状态语义与导入行为，只重构呈现层级。
const activePinia = getActivePinia()
const libraryStore = activePinia ? useLibraryStore(activePinia) : null

const statusText = computed(() => {
  switch (libraryStore?.status) {
    case 'ready':
      return '已就绪'
    case 'importing':
      return '导入中'
    case 'error':
      return '导入失败'
    case 'unavailable':
      return '未连接'
    case 'empty':
    default:
      return '待导入'
  }
})

const statusClassName = computed(() => {
  switch (libraryStore?.status) {
    case 'ready':
      return 'status-pill--ready'
    case 'importing':
      return 'status-pill--importing'
    case 'error':
      return 'status-pill--error'
    default:
      return 'status-pill--empty'
  }
})

const metricText = computed(() => `${libraryStore?.totalDocuments ?? 0} 篇文献`)

onMounted(() => {
  if (!libraryStore) {
    return
  }

  void libraryStore.refreshDocuments()
})
</script>

<template>
  <section class="knowledge-bar" data-testid="knowledge-bar" aria-label="知识库状态条">
    <div class="knowledge-proof">
      <p class="knowledge-label">知识库</p>
      <p class="knowledge-proof-text">为当前论文草稿提供检索与论证参考</p>
    </div>

    <div class="knowledge-side">
      <div class="knowledge-metrics" aria-label="知识库状态与规模">
        <span class="status-pill" :class="statusClassName">{{ statusText }}</span>
        <span class="metric-text">{{ metricText }}</span>
      </div>

      <ImportPdfButton />
    </div>
  </section>
</template>

<style scoped>
.knowledge-bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: rgba(37, 99, 235, 0.06);
}

.knowledge-proof {
  min-width: 0;
  padding-top: 2px;
}

.knowledge-label {
  font-size: var(--font-size-caption);
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--color-accent);
}

.knowledge-proof-text {
  margin-top: 4px;
  font-size: var(--font-size-body);
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.5;
}

.knowledge-side {
  display: grid;
  gap: var(--space-2);
  width: min(100%, 250px);
}

.knowledge-metrics {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  justify-content: flex-end;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: var(--font-size-caption);
  font-weight: 600;
}

.status-pill--empty {
  background: var(--color-surface-base);
  color: var(--color-accent);
}

.status-pill--ready {
  background: rgba(18, 183, 106, 0.12);
  color: #067647;
}

.status-pill--importing {
  background: rgba(245, 158, 11, 0.14);
  color: #b54708;
}

.status-pill--error {
  background: rgba(180, 35, 24, 0.12);
  color: #b42318;
}

.metric-text {
  font-size: var(--font-size-caption);
  color: var(--color-text-secondary);
}
</style>
