<template>
  <div class="user-message">
    <div class="user-bubble">
      {{ message.content }}
    </div>
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
  max-width: 70%;
  padding: var(--claude-spacing-md) var(--claude-spacing-lg);
  background: var(--claude-primary);
  color: white;
  border-radius: var(--claude-radius-lg);
  border-bottom-right-radius: var(--claude-radius-sm);
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}
</style>
