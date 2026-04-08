<script setup lang="ts">
import SourceCardList, { type SourceCard } from './SourceCardList.vue'

/**
 * 助手回复消息。
 *
 * Task 7 的关键语义：
 * - “来源”不是附件栏，而是回复正文的一部分；
 *   因此 SourceCardList 必须在本组件内部渲染。
 * - 这是论文创作 RAG 辅助插件的回复形态，不是通用聊天气泡。
 */
export interface AssistantAnswerMessage {
  id: string
  role: 'assistant'

  /**
   * kind 用于区分“回复/错误/系统提示”等后续扩展。
   * Task 7 先只用 answer。
   */
  kind: 'answer'

  /**
   * 回复正文（第一版只支持纯文本）。
   */
  content: string

  /**
   * ISO 时间字符串。
   */
  createdAt: string

  /**
   * 参考来源列表。
   */
  sources?: SourceCard[]
}

defineProps<{
  message: AssistantAnswerMessage
}>()
</script>

<template>
  <article class="assistant-message" data-testid="assistant-message" aria-label="助手回复">
    <div class="bubble">
      <p class="content">{{ message.content }}</p>

      <SourceCardList v-if="message.sources?.length" :sources="message.sources" />
    </div>
  </article>
</template>

<style scoped>
.assistant-message {
  display: flex;
  justify-content: flex-start;
}

.bubble {
  width: 100%;
  padding: 14px 16px;
  border-radius: 16px 16px 16px 4px;
  border: 1px solid var(--color-border-subtle);
  background: var(--color-surface-base);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}

.content {
  color: var(--color-text-primary);
  line-height: 1.8;
  white-space: pre-wrap;
}
</style>
