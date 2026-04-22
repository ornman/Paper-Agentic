<template>
  <div class="app-container">
    <header class="app-header">
      <h1 class="app-title">论文助手</h1>
      <div class="tab-group">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'chat' }"
          @click="activeTab = 'chat'"
        >
          对话
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'library' }"
          @click="activeTab = 'library'"
        >
          文献库
        </button>
      </div>
      <button v-if="activeTab === 'chat'" class="reset-btn" @click="handleReset" title="开始新对话">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 2a6 6 0 1 0 6 6h-2a4 4 0 1 1-4-4V2z"/>
          <path d="M8 0v5l3.5 3.5L8 0z"/>
        </svg>
        新对话
      </button>
    </header>

    <ChatView v-if="activeTab === 'chat'" />
    <LibraryView v-else />
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
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f4f0;
}

.app-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: white;
  border-bottom: 1px solid #e5e5e5;
  flex-shrink: 0;
}

.app-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
  white-space: nowrap;
}

.tab-group {
  display: flex;
  gap: 0;
  background: #f0f0f0;
  border-radius: 6px;
  padding: 2px;
  flex: 1;
}

.tab-btn {
  flex: 1;
  padding: 5px 12px;
  background: transparent;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: white;
  color: #1a1a1a;
  font-weight: 500;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.tab-btn:hover:not(.active) {
  color: #333;
}

.reset-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  font-size: 12px;
  color: #595959;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.reset-btn:hover {
  background: #e6e6e6;
  border-color: #b3b3b3;
}
</style>
