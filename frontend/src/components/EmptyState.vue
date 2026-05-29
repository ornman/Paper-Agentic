<template>
  <div class="empty-state">
    <h1 class="empty-title">{{ greeting.title }}</h1>
    <p class="empty-hint">{{ greeting.hint }}</p>
    <div class="prompt-container">
      <button class="shuffle-btn" :class="{ spinning }" type="button" @click="handleShuffle" title="换一批">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="18" height="18" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
          <path d="M42 8v16M6 24v16m36-16c0-9.941-8.059-18-18-18a17.95 17.95 0 0 0-12.952 5.5M6 24c0 9.941 8.059 18 18 18a17.94 17.94 0 0 0 12.5-5.048" />
        </svg>
      </button>
      <TransitionGroup name="card" tag="div" class="prompt-grid">
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
      </TransitionGroup>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import iconDocText from '../assets/icons/document-text.svg?raw'
import iconSearch from '../assets/icons/search-sparkle.svg?raw'
import iconEdit from '../assets/icons/clipboard-edit.svg?raw'
import iconChart from '../assets/icons/chart-multiple.svg?raw'
import iconBot from '../assets/icons/bot-sparkle.svg?raw'
import iconTextSparkle from '../assets/icons/text-sparkle.svg?raw'

const emit = defineEmits<{
  (e: 'select-prompt', text: string): void
}>()

interface PromptCard {
  icon: string
  title: string
  description: string
  prompt: string
}

const allPromptCards: PromptCard[] = [
  // ── 功能导向 ──
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
  // ── 痛点导向（用户原声） ──
  {
    icon: iconTextSparkle,
    title: '写了一半卡住了...',
    description: '不知道怎么往下写，帮你梳理思路',
    prompt: '我写论文写了一半卡住了，帮我梳理思路，找到继续写下去的方向',
  },
  {
    icon: iconSearch,
    title: '我写的有文献支撑吗？',
    description: '检查你的论点能否被文献库支持',
    prompt: '帮我检查一下我写的这些观点，在文献库中有没有论文可以支持',
  },
  {
    icon: iconDocText,
    title: '综述咋写啊？',
    description: '和你探讨综述的写作框架和逻辑脉络',
    prompt: '我想写文献综述但不知道怎么组织，能不能和我探讨一下写作框架和逻辑脉络',
  },
  {
    icon: iconEdit,
    title: '帮我把这段改学术一点',
    description: '优化措辞和逻辑，让表达更专业',
    prompt: '帮我把这段话改得更学术更专业，优化措辞和逻辑',
  },
  {
    icon: iconBot,
    title: '我的创新点够不够？',
    description: '对比已有文献，评估研究创新性',
    prompt: '帮我对比已有文献，分析我的研究创新点够不够',
  },
  {
    icon: iconChart,
    title: '这个选题还能发吗？',
    description: '从研究空白、竞争热度帮你评估选题',
    prompt: '帮我分析一下这个选题的研究空白和竞争热度，看看还有没有发表空间',
  },
]

// 随机选取 6 个展示（每次组件挂载重新随机）
const promptCards = ref<PromptCard[]>([])
const spinning = ref(false)

function shuffle() {
  promptCards.value = [...allPromptCards].sort(() => Math.random() - 0.5).slice(0, 6)
}

function handleShuffle() {
  if (spinning.value) return
  spinning.value = true
  shuffle()
  setTimeout(() => { spinning.value = false }, 400)
}

shuffle()

// 轮询问候语
const greetings = [
  { title: '今天有什么可以帮到你？', hint: '输入你的问题，开始与论文对话' },
  { title: '探索学术文献，从这里开始', hint: '输入研究问题，开启智能文献分析与学术写作辅助' },
  { title: '准备好深入论文了吗？', hint: '选择下方快捷指令，或直接输入你的研究问题' },
]
const greeting = greetings[Math.floor(Math.random() * greetings.length)]
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

.prompt-container {
  max-width: 680px;
  width: 100%;
}

.shuffle-btn {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  width: 100%;
  margin-bottom: 8px;
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  padding: 0;
  opacity: 0.5;
  transition: opacity 150ms ease, color 150ms ease;
}

.shuffle-btn:hover {
  opacity: 1;
  color: var(--color-accent);
}

.shuffle-btn.spinning svg {
  animation: spin-once 0.4s ease;
}

@keyframes spin-once {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3, 12px);
  position: relative;
}

@media (max-width: 640px) {
  .prompt-container .prompt-grid {
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

  .prompt-container .prompt-grid {
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

/* 卡片切换动画 */
.card-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.card-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
  position: absolute;
}

.card-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.card-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
