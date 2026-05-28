<template>
  <div class="empty-state">
    <h1 class="empty-title">今天有什么可以帮到你？</h1>
    <p class="empty-hint">输入你的问题，开始与论文对话</p>
    <div class="prompt-grid">
      <button
        v-for="card in promptCards"
        :key="card.title"
        class="prompt-card"
        type="button"
        @click="emit('select-prompt', card.prompt)"
      >
        <span class="prompt-card-icon" v-html="card.icon" />
        <div class="prompt-card-body">
          <div class="prompt-card-title">{{ card.title }}</div>
          <div class="prompt-card-desc">{{ card.description }}</div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import iconDocText from '../assets/icons/document-text.svg?raw'
import iconSearch from '../assets/icons/search-sparkle.svg?raw'
import iconEdit from '../assets/icons/clipboard-edit.svg?raw'
import iconChart from '../assets/icons/chart-multiple.svg?raw'
import iconBot from '../assets/icons/bot-sparkle.svg?raw'
import iconTextSparkle from '../assets/icons/text-sparkle.svg?raw'

const emit = defineEmits<{
  (e: 'select-prompt', text: string): void
}>()

const promptCards = [
  {
    icon: iconDocText,
    title: '帮我分析这篇论文',
    description: '解读论文的核心贡献、方法和实验设计',
    prompt: '帮我分析这篇论文的核心贡献、方法和实验设计',
  },
  {
    icon: iconSearch,
    title: '查找相关文献',
    description: '基于当前研究主题检索相关论文',
    prompt: '帮我查找与当前研究主题相关的文献',
  },
  {
    icon: iconEdit,
    title: '改进我的表达',
    description: '优化学术写作的措辞和逻辑结构',
    prompt: '帮我改进学术写作的措辞和逻辑结构',
  },
  {
    icon: iconChart,
    title: '解释实验结果',
    description: '帮助分析和解读实验数据',
    prompt: '帮我分析和解读实验数据',
  },
  {
    icon: iconBot,
    title: '生成研究思路',
    description: '基于已有文献提出新的研究方向',
    prompt: '基于已有文献帮我提出新的研究方向',
  },
  {
    icon: iconTextSparkle,
    title: '生成文献综述',
    description: '自动汇总多篇论文的核心观点',
    prompt: '帮我汇总多篇论文的核心观点，生成文献综述',
  },
]
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 60vh;
  text-align: center;
  user-select: none;
}

.empty-title {
  font-size: 26px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
  letter-spacing: -0.3px;
}

.empty-hint {
  font-size: 14px;
  color: var(--color-text-muted);
  margin-bottom: var(--space-6, 24px);
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3, 12px);
  max-width: 680px;
  width: 100%;
}

@media (max-width: 640px) {
  .prompt-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 420px) {
  .empty-state {
    min-height: 50vh;
    padding: var(--space-4);
  }

  .empty-title {
    font-size: 22px;
  }

  .prompt-grid {
    grid-template-columns: 1fr;
  }
}

.prompt-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3, 12px);
  padding: var(--space-4, 16px);
  text-align: left;
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md, 10px);
  cursor: pointer;
  transition: border-color 150ms ease, background 150ms ease, box-shadow 150ms ease;
}

.prompt-card:hover {
  border-color: var(--color-accent);
  background: var(--color-accent-soft, rgba(59, 130, 246, 0.06));
  box-shadow: var(--shadow-sm);
}

.prompt-card-icon {
  display: flex;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  margin-top: 2px;
}

.prompt-card-icon :deep(svg) {
  width: 100%;
  height: 100%;
}

.prompt-card-body {
  min-width: 0;
}

.prompt-card-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.4;
}

.prompt-card-desc {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 4px;
  line-height: 1.4;
}
</style>
