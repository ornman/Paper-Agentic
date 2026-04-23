<template>
  <div class="user-message">
    <div class="user-bubble">{{ message.content }}</div>
  </div>
</template>

<script setup lang="ts">
import type { ConversationUserActionMessage } from '../stores/conversation'

defineProps<{
  message: ConversationUserActionMessage
}>()
</script>

<style scoped>
.user-message {
  display: flex;
  justify-content: flex-end;
}

.user-bubble {
  max-width: 75%;
  padding: var(--space-3) var(--space-4);
  background: var(--color-user-bubble);
  color: var(--color-user-bubble-text);
  border-radius: var(--radius-lg);
  border-bottom-right-radius: 6px;
  font-size: var(--font-size-body);
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}
</style>
