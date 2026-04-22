<template>
  <div class="claude-app">
    <!-- 顶部 Tab 导航 -->
    <nav class="claude-nav">
      <div class="claude-nav-container">
        <button
          :class="['claude-tab', { 'claude-tab-active': activeTab === 'chat' }]"
          @click="activeTab = 'chat'"
        >
          <span class="claude-tab-icon">💬</span>
          <span class="claude-tab-label">对话</span>
        </button>
        <button
          :class="['claude-tab', { 'claude-tab-active': activeTab === 'library' }]"
          @click="activeTab = 'library'"
        >
          <span class="claude-tab-icon">📚</span>
          <span class="claude-tab-label">文献库</span>
        </button>
        <button v-if="activeTab === 'chat'" class="claude-reset-btn" @click="handleReset" title="开始新对话">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 2a6 6 0 1 0 6 6h-2a4 4 0 1 1-4-4V2z"/>
            <path d="M8 0v5l3.5 3.5L8 0z"/>
          </svg>
          <span>新对话</span>
        </button>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main class="claude-main">
      <ChatView v-if="activeTab === 'chat'" />
      <LibraryView v-else />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useConversationStore } from './stores/conversation'
import ChatView from './views/ChatView.vue'
import LibraryView from './views/LibraryView.vue'

const activeTab = ref<'chat' | 'library'>('chat')
const conversationStore = useConversationStore()

function handleReset() {
  if (conversationStore.messages.length > 0 &&
      (conversationStore.status === 'requesting' || conversationStore.status === 'streaming')) {
    if (!confirm('当前对话正在进行中，确定要开始新对话吗？')) return
  }
  conversationStore.reset()
}
</script>

<style scoped>
.claude-app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--claude-bg-main);
}

.claude-nav {
  background: var(--claude-bg-card);
  border-bottom: 1px solid var(--claude-border);
  padding: var(--claude-spacing-sm) 0;
  flex-shrink: 0;
}

.claude-nav-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--claude-spacing-lg);
  display: flex;
  gap: var(--claude-spacing-sm);
  align-items: center;
}

.claude-tab {
  display: flex;
  align-items: center;
  gap: var(--claude-spacing-sm);
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  border-radius: var(--claude-radius-md);
  color: var(--claude-text-secondary);
  font-weight: 500;
  font-size: 14px;
  transition: all 0.2s ease;
}

.claude-tab:hover {
  background: var(--claude-bg-muted);
  color: var(--claude-text-primary);
}

.claude-tab-active {
  background: var(--claude-primary-light);
  color: var(--claude-primary);
}

.claude-tab-icon {
  font-size: 18px;
}

.claude-tab-label {
  font-size: 14px;
}

.claude-reset-btn {
  display: flex;
  align-items: center;
  gap: var(--claude-spacing-xs);
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  background: var(--claude-bg-muted);
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  font-size: 12px;
  color: var(--claude-text-secondary);
  margin-left: auto;
  white-space: nowrap;
}

.claude-reset-btn:hover {
  background: var(--claude-primary-light);
  border-color: var(--claude-primary);
  color: var(--claude-primary);
}

.claude-main {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: var(--claude-spacing-lg);
  display: flex;
  flex-direction: column;
}
</style>
