<script setup lang="ts">
import { watch, nextTick, ref } from 'vue'
import { useMockStore } from '../../stores/mockStore'
import MessageItem from './MessageItem.vue'

const store = useMockStore()
const listRef = ref<HTMLDivElement | null>(null)

// 自动滚动到底部
watch(
  () => store.activeSession?.messages.length,
  () => {
    nextTick(() => {
      if (listRef.value) {
        listRef.value.scrollTop = listRef.value.scrollHeight
      }
    })
  }
)
</script>

<template>
  <div ref="listRef" class="message-list">
    <div v-if="store.activeSession?.messages.length" class="messages">
      <MessageItem
        v-for="msg in store.activeSession?.messages"
        :key="msg.id"
        :message="msg"
      />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon">💬</div>
      <div class="empty-text">开始对话吧！</div>
      <div class="empty-hint">输入问题，AI 将基于您的文献库生成回答</div>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.messages {
  max-width: 800px;
  margin: 0 auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 18px;
  margin-bottom: 8px;
  color: var(--text-primary);
}

.empty-hint {
  font-size: 14px;
}
</style>
