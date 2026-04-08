<script setup lang="ts">
import { computed } from 'vue'

/**
 * 来源卡片：用于承载“助手回复”引用的文献片段。
 *
 * 设计约束（Task 7）：
 * 1) 来源区是“回复正文的一部分”，因此由 AssistantMessage 组件内嵌渲染；
 * 2) 第一版只做展示，不做跳转、不做展开折叠、不做复制按钮；
 * 3) 单会话场景下，来源卡片不需要全局 store，直接走 props 即可。
 */
export interface SourceCard {
  /**
   * 稳定主键：后续会用于列表更新与动画。
   */
  id: string

  /**
   * 文献标题（或知识库条目标题）。
   */
  title: string

  /**
   * 页码：用于让用户回到 PDF/文献定位。
   * 第一版允许为空（例如来源来自网页或未解析页码）。
   */
  page?: number

  /**
   * 引用片段：帮助用户快速判断该来源是否可信、是否与当前写作方向有关。
   */
  snippet: string
}

const props = defineProps<{
  sources: SourceCard[]
}>()

// 这里做一个最小的“是否存在来源”判断：
// - 组件仍然可被挂载（方便测试 / 占位）
// - 但没有来源时不渲染列表内容
const hasSources = computed(() => props.sources.length > 0)
</script>

<template>
  <section class="source-card-list" data-testid="source-card-list" aria-label="参考来源">
    <p class="heading">参考来源</p>

    <ul v-if="hasSources" class="cards">
      <li v-for="source in sources" :key="source.id" class="card">
        <p class="meta">
          <span class="title">{{ source.title }}</span>
          <span v-if="typeof source.page === 'number'" class="page">第 {{ source.page }} 页</span>
        </p>

        <p class="snippet">{{ source.snippet }}</p>
      </li>
    </ul>

    <p v-else class="empty-hint">暂无可展示的来源。</p>
  </section>
</template>

<style scoped>
.source-card-list {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-subtle);
}

.heading {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.cards {
  list-style: none;
  display: grid;
  gap: var(--space-2);
}

.card {
  padding: 10px 12px;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  background: var(--color-surface-base);
}

.meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.title {
  font-weight: 600;
  color: var(--color-text-primary);
}

.page {
  font-size: var(--font-size-caption);
  color: var(--color-text-secondary);
}

.snippet {
  margin-top: 6px;
  font-size: var(--font-size-caption);
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.empty-hint {
  font-size: var(--font-size-caption);
  color: var(--color-text-secondary);
}
</style>
