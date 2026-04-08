<script setup lang="ts">
import { watch, nextTick, ref } from 'vue'
import { useMockStore } from '../../stores/mockStore'
import MessageItem from './MessageItem.vue'

const store = useMockStore()
const listRef = ref<HTMLDivElement | null>(null)

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
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </div>
      <div class="empty-title">开始对话</div>
      <div class="empty-hint">输入问题，基于您的文献库获取回答</div>
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
  max-width: 100%;
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
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 148, 136, 0.1);
  border-radius: 50%;
  margin-bottom: 16px;
}

.empty-icon svg {
  width: 32px;
  height: 32px;
  color: var(--primary);
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-primary);
}

.empty-hint {
  font-size: 13px;
}
</style>
