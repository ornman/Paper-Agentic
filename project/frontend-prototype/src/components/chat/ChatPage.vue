<script setup lang="ts">
import SessionList from './SessionList.vue'
import MessageList from './MessageList.vue'
import ChatInput from './ChatInput.vue'
</script>

<template>
  <div class="chat-page">
    <SessionList />
    <MessageList />
    <ChatInput />
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}
</style>
