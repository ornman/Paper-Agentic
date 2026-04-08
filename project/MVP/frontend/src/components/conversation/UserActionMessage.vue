<script setup lang="ts">
/**
 * 用户动作消息（不是普通聊天输入）。
 *
 * 现阶段同时承接两类用户侧消息：
 * - action：场景化动作，例如“获取灵感”
 * - prompt：用户直接输入的问题
 */
export interface UserActionMessage {
  id: string
  role: 'user'

  /**
   * kind 用于区分“动作/普通输入”。
   */
  kind: 'action' | 'prompt'

  /**
   * 动作描述，例如“基于当前论文草稿获取灵感”。
   */
  content: string

  createdAt: string
}

const props = defineProps<{
  message: UserActionMessage
}>()
</script>

<template>
  <article class="user-action-message" data-testid="user-action-message" aria-label="用户消息">
    <div class="bubble">
      <p class="eyebrow">{{ props.message.kind === 'prompt' ? '用户提问' : '触发动作' }}</p>
      <p class="content">{{ props.message.content }}</p>
    </div>
  </article>
</template>

<style scoped>
.user-action-message {
  display: flex;
  justify-content: flex-end;
}

.bubble {
  max-width: min(85%, 320px);
  padding: 12px 14px;
  border-radius: 16px 16px 4px 16px;
  background: var(--color-accent);
  color: #ffffff;
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.16);
}

.eyebrow {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.78);
}

.content {
  margin-top: 6px;
  color: #ffffff;
  line-height: 1.7;
  white-space: pre-wrap;
}
</style>
