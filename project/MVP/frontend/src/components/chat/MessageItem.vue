<script setup lang="ts">
import type { MockMessage } from '../../stores/mockStore'

defineProps<{
  message: MockMessage
}>()
</script>

<template>
  <div :class="['message', message.role]">
    <div class="message-avatar">
      <svg v-if="message.role === 'user'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </svg>
      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M7.5 13A1.5 1.5 0 0 0 6 14.5 1.5 1.5 0 0 0 7.5 16 1.5 1.5 0 0 0 9 14.5 1.5 1.5 0 0 0 7.5 13m9 0a1.5 1.5 0 0 0-1.5 1.5 1.5 1.5 0 0 0 1.5 1.5 1.5 1.5 0 0 0 1.5-1.5 1.5 1.5 0 0 0-1.5-1.5M12 9a1 1 0 0 0-1 1 1 1 0 0 0 1 1 1 1 0 0 0 1-1 1 1 0 0 0-1-1z"/>
      </svg>
    </div>
    <div class="message-body">
      <div class="message-content">{{ message.content }}</div>
      <!-- 来源卡片 -->
      <div v-if="message.sources && message.sources.length > 0" class="sources">
        <div class="sources-title">
          <svg class="sources-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
          参考文献 ({{ message.sources.length }})
        </div>
        <div class="source-cards">
          <div v-for="source in message.sources" :key="source.id" class="source-card">
            <div class="source-header">
              <span class="source-doc">
                <svg class="doc-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14,2 14,8 20,8"/>
                </svg>
                {{ source.documentName }}
              </span>
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
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--bg-input);
}

.message.user .message-avatar {
  background: var(--primary);
  color: white;
}

.message.assistant .message-avatar {
  background: rgba(13, 148, 136, 0.1);
  color: var(--primary);
}

.message-avatar svg {
  width: 18px;
  height: 18px;
}

.message-body {
  max-width: 80%;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  line-height: 1.6;
  white-space: pre-wrap;
  font-size: 13px;
}

.message.user .message-content {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.sources {
  margin-top: 12px;
}

.sources-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.sources-icon {
  width: 16px;
  height: 16px;
}

.source-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.source-card {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.source-card:hover {
  border-color: var(--primary);
  background: rgba(13, 148, 136, 0.05);
}

.source-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
}

.source-doc {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--primary);
  font-weight: 500;
}

.doc-icon {
  width: 14px;
  height: 14px;
}

.source-page {
  color: var(--text-secondary);
  background: var(--bg-card);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.source-content {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  border-left: 2px solid var(--primary-light);
  padding-left: 10px;
}
</style>
