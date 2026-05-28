<template>
  <div class="user-message">
    <div class="user-bubble">{{ message.content }}</div>
  </div>
</template>

<script setup lang="ts">
import type { UserMessage as UserMessageType } from '../stores/conversation'

defineProps<{
  message: UserMessageType
}>()
</script>

<style scoped>
.user-message {
  display: flex;
  justify-content: flex-end;
  margin: 12px 0;
}

.user-bubble {
  max-width: 80%;
  padding: 10px 16px;
  background: var(--color-accent);
  color: #ffffff;
  border-radius: 18px 18px 6px 18px;
  font-size: var(--font-size-body);
  line-height: 1.65;
  word-break: break-word;
  white-space: pre-wrap;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.2);
}
</style>
