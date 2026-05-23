<script setup lang="ts">
import AssistantMessage, { type AssistantAnswerMessage } from './AssistantMessage.vue'
import UserActionMessage, { type UserActionMessage as UserActionMessageRecord } from './UserActionMessage.vue'

/**
 * 单会话消息列表（Task 7）。
 *
 * 设计边界：
 * - 只负责“展示当前会话中的消息序列”，不负责加载历史会话；
 * - 不接 SSE（那是 Task 8）；
 * - 不在这里读写 Pinia store，避免展示组件和状态管理强耦合。
 */
export type ConversationUiMessage = UserActionMessageRecord | AssistantAnswerMessage

defineProps<{
  messages: ConversationUiMessage[]
}>()
</script>

<template>
  <section class="message-list" data-testid="message-list" aria-label="单会话消息列表">
    <div v-for="message in messages" :key="message.id" class="message-row">
      <!--
        data-testid 约定：测试只关心“列表渲染顺序”和“角色语义”，
        因此把识别信息放在 MessageList 的稳定 DOM 外壳上，避免子组件结构变动导致测试脆弱。
      -->
      <div
        class="message-shell"
        data-testid="conversation-message"
        :data-message-role="message.role"
        :data-message-kind="message.kind"
      >
        <UserActionMessage v-if="message.role === 'user'" :message="message" />
        <AssistantMessage v-else-if="message.role === 'assistant'" :message="message" />

        <!-- 兜底：未来如果引入 system/error 类型，也不会直接炸掉页面。 -->
        <p v-else class="unknown-message">暂不支持的消息类型</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.message-list {
  display: grid;
  gap: var(--space-3);
}

.message-row {
  display: block;
}

.message-shell {
  width: 100%;
}

.unknown-message {
  padding: 12px 14px;
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
}
</style>
