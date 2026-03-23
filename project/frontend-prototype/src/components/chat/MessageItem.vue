<script setup lang="ts">
import type { MockMessage } from '../../stores/mockStore'

defineProps<{
  message: MockMessage
}>()
</script>

<template>
  <div :class="['message', message.role]">
    <div class="message-avatar">
      {{ message.role === 'user' ? '👤' : '🤖' }}
    </div>
    <div class="message-body">
      <div class="message-content">{{ message.content }}</div>
      <!-- 来源卡片 -->
      <div v-if="message.sources && message.sources.length > 0" class="sources">
        <div class="sources-title">📚 来源 ({{ message.sources.length }})</div>
        <div class="source-cards">
          <div v-for="source in message.sources" :key="source.id" class="source-card">
            <div class="source-header">
              <span class="source-doc">{{ source.documentName }}</span>
              <span class="source-page">第 {{ source.page }} 页</span>
            </div>
            <div class="source-content">{{ source.content }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  padding: 16px 0;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.message-body {
  max-width: 80%;
}

.message.user .message-body {
  align-items: flex-end;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  background: var(--bg-input);
  line-height: 1.6;
  white-space: pre-wrap;
}

.message.user .message-content {
  background: var(--primary);
}

.sources {
  margin-top: 12px;
}

.sources-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.source-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.source-card {
  background: var(--bg-sidebar);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.source-card:hover {
  border-color: var(--primary);
}

.source-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
}

.source-doc {
  color: var(--primary);
  font-weight: 500;
}

.source-page {
  color: var(--text-secondary);
}

.source-content {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
</style>
