# 前端 UI 原型实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建一个纯前端 Vue 3 展示界面，用于演示 WPS 论文写作辅助工具的 UI 效果。

**Architecture:** 标签页切换布局，三个独立页面（导入/对话/设置），使用 Pinia 管理模拟数据，纯 CSS 实现现代 AI 助手风格。

**Tech Stack:** Vue 3 + TypeScript + Vite + Pinia + 纯 CSS

---

## Task 1: 项目初始化

**Files:**
- Create: `D:/同步/project/frontend-prototype/package.json`
- Create: `D:/同步/project/frontend-prototype/vite.config.ts`
- Create: `D:/同步/project/frontend-prototype/tsconfig.json`
- Create: `D:/同步/project/frontend-prototype/index.html`
- Create: `D:/同步/project/frontend-prototype/src/main.ts`
- Create: `D:/同步/project/frontend-prototype/src/App.vue`
- Create: `D:/同步/project/frontend-prototype/src/style.css`

**Step 1: 创建项目目录**

```bash
mkdir -p D:/同步/project/frontend-prototype/src/components/{layout,ingest,chat,settings}
mkdir -p D:/同步/project/frontend-prototype/src/stores
```

**Step 2: 创建 package.json**

```json
{
  "name": "wps-thesis-prototype",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "pinia": "^2.1.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vue-tsc": "^2.0.0"
  }
}
```

**Step 3: 创建 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000
  }
})
```

**Step 4: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**Step 5: 创建 tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

**Step 6: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>WPS 论文写作辅助 - UI 原型</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

**Step 7: 创建 src/main.ts**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
```

**Step 8: 创建 src/style.css（基础样式）**

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --primary: #10a37f;
  --primary-hover: #0d8a6a;
  --bg-main: #343541;
  --bg-sidebar: #202123;
  --bg-input: #40414f;
  --text-primary: #ececf1;
  --text-secondary: #c5c5d2;
  --border: #4e4f60;
  --error: #ef4444;
  --success: #10a37f;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg-main);
  color: var(--text-primary);
  line-height: 1.5;
}

#app {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
```

**Step 9: 安装依赖**

```bash
cd D:/同步/project/frontend-prototype
pnpm install
```

**Step 10: 验证项目启动**

```bash
pnpm dev
```

Expected: 服务启动在 http://localhost:3000

---

## Task 2: 模拟数据 Store

**Files:**
- Create: `D:/同步/project/frontend-prototype/src/stores/mockStore.ts`

**Step 1: 创建模拟数据 Store**

```typescript
// src/stores/mockStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 模拟文档类型
export interface MockDocument {
  id: string
  name: string
  path: string
  pages: number
  status: 'pending' | 'processing' | 'completed' | 'error'
  progress: number
}

// 模拟消息类型
export interface MockMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: MockSource[]
  timestamp: Date
}

// 模拟来源类型
export interface MockSource {
  id: string
  documentName: string
  page: number
  content: string
}

// 模拟会话类型
export interface MockSession {
  id: string
  title: string
  messages: MockMessage[]
  createdAt: Date
}

export const useMockStore = defineStore('mock', () => {
  // 状态
  const activeTab = ref<'ingest' | 'chat' | 'settings'>('chat')
  const documents = ref<MockDocument[]>([
    { id: '1', name: '深度学习综述.pdf', path: 'D:/papers/dl-survey.pdf', pages: 45, status: 'completed', progress: 100 },
    { id: '2', name: '注意力机制详解.pdf', path: 'D:/papers/attention.pdf', pages: 23, status: 'completed', progress: 100 },
  ])

  const sessions = ref<MockSession[]>([
    {
      id: '1',
      title: '论文写作讨论',
      messages: [
        { id: '1', role: 'user', content: '什么是注意力机制？', timestamp: new Date() },
        {
          id: '2',
          role: 'assistant',
          content: '注意力机制（Attention Mechanism）是深度学习中的一种关键技术，它允许模型在处理序列数据时，动态地关注输入的不同部分。\n\n核心思想是让模型学会"关注"重要的信息，而忽略不相关的部分。在自然语言处理中，注意力机制可以帮助模型理解词语之间的关系。',
          sources: [
            { id: 's1', documentName: '注意力机制详解.pdf', page: 3, content: '注意力机制允许模型动态地关注输入的不同部分...' },
            { id: 's2', documentName: '深度学习综述.pdf', page: 12, content: 'Attention is a mechanism that allows the model to focus...' }
          ],
          timestamp: new Date()
        }
      ],
      createdAt: new Date()
    },
    {
      id: '2',
      title: '文献调研',
      messages: [],
      createdAt: new Date()
    }
  ])

  const activeSessionId = ref('1')
  const isStreaming = ref(false)
  const importProgress = ref(0)

  // 计算属性
  const activeSession = computed(() =>
    sessions.value.find(s => s.id === activeSessionId.value)
  )

  // 动作
  function setActiveTab(tab: 'ingest' | 'chat' | 'settings') {
    activeTab.value = tab
  }

  function setActiveSession(id: string) {
    activeSessionId.value = id
  }

  function addMessage(message: MockMessage) {
    const session = sessions.value.find(s => s.id === activeSessionId.value)
    if (session) {
      session.messages.push(message)
    }
  }

  function simulateImport(callback: (progress: number) => void) {
    importProgress.value = 0
    const interval = setInterval(() => {
      importProgress.value += 10
      callback(importProgress.value)
      if (importProgress.value >= 100) {
        clearInterval(interval)
      }
    }, 200)
  }

  function simulateStreamResponse(userMessage: string) {
    isStreaming.value = true

    // 添加用户消息
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    })

    // 模拟 AI 响应
    const aiResponse = '这是一个模拟的 AI 响应。在实际系统中，这里会显示基于您私有文献库生成的内容，并附带来源引用。'
    const messageId = (Date.now() + 1).toString()

    // 添加空的 AI 消息
    addMessage({
      id: messageId,
      role: 'assistant',
      content: '',
      timestamp: new Date()
    })

    // 逐字显示
    let index = 0
    const interval = setInterval(() => {
      const session = sessions.value.find(s => s.id === activeSessionId.value)
      const msg = session?.messages.find(m => m.id === messageId)
      if (msg && index < aiResponse.length) {
        msg.content += aiResponse[index]
        index++
      } else {
        clearInterval(interval)
        isStreaming.value = false
        // 添加来源
        if (msg) {
          msg.sources = [
            { id: 's1', documentName: '示例文档.pdf', page: 5, content: '这是相关的引用内容...' }
          ]
        }
      }
    }, 30)
  }

  return {
    // 状态
    activeTab,
    documents,
    sessions,
    activeSessionId,
    isStreaming,
    importProgress,
    // 计算属性
    activeSession,
    // 动作
    setActiveTab,
    setActiveSession,
    addMessage,
    simulateImport,
    simulateStreamResponse
  }
})
```

**Step 2: 验证编译**

```bash
cd D:/同步/project/frontend-prototype
pnpm build
```

Expected: 编译成功，无错误

---

## Task 3: 布局组件

**Files:**
- Create: `D:/同步/project/frontend-prototype/src/components/layout/TabBar.vue`
- Create: `D:/同步/project/frontend-prototype/src/components/layout/TabContent.vue`
- Modify: `D:/同步/project/frontend-prototype/src/App.vue`

**Step 1: 创建 TabBar.vue**

```vue
<!-- src/components/layout/TabBar.vue -->
<script setup lang="ts">
import { useMockStore } from '../../stores/mockStore'

const store = useMockStore()

const tabs = [
  { id: 'ingest' as const, label: '导入' },
  { id: 'chat' as const, label: '对话' },
  { id: 'settings' as const, label: '设置' }
]
</script>

<template>
  <div class="tab-bar">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      :class="['tab-btn', { active: store.activeTab === tab.id }]"
      @click="store.setActiveTab(tab.id)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<style scoped>
.tab-bar {
  display: flex;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  flex: 1;
  padding: 12px 16px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  color: var(--text-primary);
  background: var(--bg-main);
  border-bottom: 2px solid var(--primary);
}
</style>
```

**Step 2: 创建 TabContent.vue**

```vue
<!-- src/components/layout/TabContent.vue -->
<script setup lang="ts">
import { useMockStore } from '../../stores/mockStore'
import IngestPage from '../ingest/IngestPage.vue'
import ChatPage from '../chat/ChatPage.vue'
import SettingsPage from '../settings/SettingsPage.vue'

const store = useMockStore()
</script>

<template>
  <div class="tab-content">
    <IngestPage v-if="store.activeTab === 'ingest'" />
    <ChatPage v-else-if="store.activeTab === 'chat'" />
    <SettingsPage v-else-if="store.activeTab === 'settings'" />
  </div>
</template>

<style scoped>
.tab-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
```

**Step 3: 更新 App.vue**

```vue
<!-- src/App.vue -->
<script setup lang="ts">
import TabBar from './components/layout/TabBar.vue'
import TabContent from './components/layout/TabContent.vue'
</script>

<template>
  <div class="app-container">
    <TabBar />
    <TabContent />
  </div>
</template>

<style scoped>
.app-container {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>
```

**Step 4: 验证编译**

```bash
pnpm build
```

Expected: 编译失败（缺少页面组件），这是预期的

---

## Task 4: 导入页面

**Files:**
- Create: `D:/同步/project/frontend-prototype/src/components/ingest/IngestPage.vue`

**Step 1: 创建 IngestPage.vue**

```vue
<!-- src/components/ingest/IngestPage.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import { useMockStore, type MockDocument } from '../../stores/mockStore'

const store = useMockStore()
const pdfPath = ref('')
const isImporting = ref(false)
const currentProgress = ref(0)

function handleImport() {
  if (!pdfPath.value.trim()) return

  isImporting.value = true
  currentProgress.value = 0

  // 模拟导入进度
  const interval = setInterval(() => {
    currentProgress.value += 5
    if (currentProgress.value >= 100) {
      clearInterval(interval)
      // 添加到文档列表
      const newDoc: MockDocument = {
        id: Date.now().toString(),
        name: pdfPath.value.split('/').pop() || pdfPath.value,
        path: pdfPath.value,
        pages: Math.floor(Math.random() * 50) + 10,
        status: 'completed',
        progress: 100
      }
      store.documents.push(newDoc)
      pdfPath.value = ''
      isImporting.value = false
    }
  }, 100)
}

function getStatusText(status: MockDocument['status']): string {
  const map = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    error: '错误'
  }
  return map[status]
}
</script>

<template>
  <div class="ingest-page">
    <!-- 导入区域 -->
    <div class="import-section">
      <h3>导入 PDF 文档</h3>
      <div class="input-group">
        <input
          v-model="pdfPath"
          type="text"
          placeholder="输入 PDF 文件路径，如：D:/papers/example.pdf"
          :disabled="isImporting"
        />
        <button
          @click="handleImport"
          :disabled="!pdfPath.trim() || isImporting"
          class="btn-primary"
        >
          {{ isImporting ? '导入中...' : '导入' }}
        </button>
      </div>

      <!-- 进度条 -->
      <div v-if="isImporting" class="progress-bar">
        <div class="progress-fill" :style="{ width: currentProgress + '%' }"></div>
        <span class="progress-text">{{ currentProgress }}%</span>
      </div>
    </div>

    <!-- 文档列表 -->
    <div class="doc-list">
      <h3>已导入文档 ({{ store.documents.length }})</h3>
      <div class="doc-items">
        <div v-for="doc in store.documents" :key="doc.id" class="doc-item">
          <div class="doc-icon">📄</div>
          <div class="doc-info">
            <div class="doc-name">{{ doc.name }}</div>
            <div class="doc-meta">
              <span>{{ doc.pages }} 页</span>
              <span :class="['status', doc.status]">{{ getStatusText(doc.status) }}</span>
            </div>
          </div>
        </div>
        <div v-if="store.documents.length === 0" class="empty-state">
          暂无导入的文档
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ingest-page {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
}

.import-section {
  background: var(--bg-sidebar);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.import-section h3 {
  margin-bottom: 16px;
  font-size: 16px;
}

.input-group {
  display: flex;
  gap: 12px;
}

.input-group input {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
}

.input-group input:focus {
  outline: none;
  border-color: var(--primary);
}

.btn-primary {
  padding: 10px 20px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.progress-bar {
  margin-top: 16px;
  height: 24px;
  background: var(--bg-input);
  border-radius: 12px;
  position: relative;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  transition: width 0.1s;
}

.progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: 500;
}

.doc-list {
  background: var(--bg-sidebar);
  border-radius: 8px;
  padding: 20px;
}

.doc-list h3 {
  margin-bottom: 16px;
  font-size: 16px;
}

.doc-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-input);
  border-radius: 6px;
}

.doc-icon {
  font-size: 24px;
}

.doc-info {
  flex: 1;
}

.doc-name {
  font-size: 14px;
  margin-bottom: 4px;
}

.doc-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.status.completed {
  background: rgba(16, 163, 127, 0.2);
  color: var(--success);
}

.status.processing {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.status.error {
  background: rgba(239, 68, 68, 0.2);
  color: var(--error);
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
</style>
```

**Step 2: 验证编译**

```bash
pnpm build
```

Expected: 编译失败（缺少其他页面组件），这是预期的

---

## Task 5: 对话页面

**Files:**
- Create: `D:/同步/project/frontend-prototype/src/components/chat/ChatPage.vue`
- Create: `D:/同步/project/frontend-prototype/src/components/chat/SessionList.vue`
- Create: `D:/同步/project/frontend-prototype/src/components/chat/MessageList.vue`
- Create: `D:/同步/project/frontend-prototype/src/components/chat/MessageItem.vue`
- Create: `D:/同步/project/frontend-prototype/src/components/chat/ChatInput.vue`

**Step 1: 创建 MessageItem.vue**

```vue
<!-- src/components/chat/MessageItem.vue -->
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
```

**Step 2: 创建 MessageList.vue**

```vue
<!-- src/components/chat/MessageList.vue -->
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
```

**Step 3: 创建 ChatInput.vue**

```vue
<!-- src/components/chat/ChatInput.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import { useMockStore } from '../../stores/mockStore'

const store = useMockStore()
const inputText = ref('')
const mode = ref<'qa' | 'continue'>('qa')

function handleSend() {
  if (!inputText.value.trim() || store.isStreaming) return
  store.simulateStreamResponse(inputText.value)
  inputText.value = ''
}
</script>

<template>
  <div class="chat-input">
    <div class="mode-switch">
      <button
        :class="['mode-btn', { active: mode === 'qa' }]"
        @click="mode = 'qa'"
      >
        问答模式
      </button>
      <button
        :class="['mode-btn', { active: mode === 'continue' }]"
        @click="mode = 'continue'"
      >
        续写模式
      </button>
    </div>
    <div class="input-row">
      <textarea
        v-model="inputText"
        placeholder="输入问题或续写提示..."
        @keydown.enter.exact.prevent="handleSend"
        :disabled="store.isStreaming"
        rows="1"
      ></textarea>
      <button
        @click="handleSend"
        :disabled="!inputText.trim() || store.isStreaming"
        class="send-btn"
      >
        {{ store.isStreaming ? '生成中...' : '发送' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  padding: 16px 20px;
  background: var(--bg-sidebar);
  border-top: 1px solid var(--border);
}

.mode-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.mode-btn {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 16px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn:hover {
  border-color: var(--text-secondary);
}

.mode-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-row textarea {
  flex: 1;
  padding: 12px 16px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
}

.input-row textarea:focus {
  outline: none;
  border-color: var(--primary);
}

.send-btn {
  padding: 12px 24px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-hover);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
```

**Step 4: 创建 SessionList.vue**

```vue
<!-- src/components/chat/SessionList.vue -->
<script setup lang="ts">
import { useMockStore } from '../../stores/mockStore'

const store = useMockStore()
</script>

<template>
  <div class="session-bar">
    <select
      :value="store.activeSessionId"
      @change="store.setActiveSession(($event.target as HTMLSelectElement).value)"
      class="session-select"
    >
      <option
        v-for="session in store.sessions"
        :key="session.id"
        :value="session.id"
      >
        {{ session.title }}
      </option>
    </select>
    <button class="new-session-btn">+ 新会话</button>
  </div>
</template>

<style scoped>
.session-bar {
  display: flex;
  gap: 12px;
  padding: 12px 20px;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border);
}

.session-select {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
}

.session-select:focus {
  outline: none;
  border-color: var(--primary);
}

.new-session-btn {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.new-session-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}
</style>
```

**Step 5: 创建 ChatPage.vue**

```vue
<!-- src/components/chat/ChatPage.vue -->
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
```

**Step 6: 验证编译**

```bash
pnpm build
```

Expected: 编译失败（缺少 SettingsPage），这是预期的

---

## Task 6: 设置页面

**Files:**
- Create: `D:/同步/project/frontend-prototype/src/components/settings/SettingsPage.vue`

**Step 1: 创建 SettingsPage.vue**

```vue
<!-- src/components/settings/SettingsPage.vue -->
<script setup lang="ts">
import { ref } from 'vue'

const serverUrl = ref('http://127.0.0.1:8000')
const llmProvider = ref('deepseek')
const model = ref('deepseek-chat')

const providers = [
  { id: 'deepseek', name: 'DeepSeek', models: ['deepseek-chat', 'deepseek-reasoner'] },
  { id: 'zhipu', name: '智谱 GLM', models: ['glm-4', 'glm-4-flash'] },
  { id: 'openai', name: 'OpenAI', models: ['gpt-4', 'gpt-3.5-turbo'] }
]

const currentProvider = () => providers.find(p => p.id === llmProvider.value)
</script>

<template>
  <div class="settings-page">
    <h2>设置</h2>

    <!-- 服务配置 -->
    <div class="settings-section">
      <h3>服务配置</h3>
      <div class="setting-item">
        <label>后端服务地址</label>
        <input v-model="serverUrl" type="text" placeholder="http://127.0.0.1:8000" />
      </div>
      <div class="setting-item">
        <label>连接状态</label>
        <span class="status-badge offline">未连接（演示模式）</span>
      </div>
    </div>

    <!-- LLM 配置 -->
    <div class="settings-section">
      <h3>语言模型配置</h3>
      <div class="setting-item">
        <label>供应商</label>
        <select v-model="llmProvider">
          <option v-for="p in providers" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
      </div>
      <div class="setting-item">
        <label>模型</label>
        <select v-model="model">
          <option v-for="m in currentProvider()?.models" :key="m" :value="m">
            {{ m }}
          </option>
        </select>
      </div>
      <div class="setting-item">
        <label>API Key</label>
        <input type="password" value="sk-****" disabled />
        <span class="hint">在真实版本中配置</span>
      </div>
    </div>

    <!-- 关于 -->
    <div class="settings-section">
      <h3>关于</h3>
      <div class="about-info">
        <p><strong>WPS 论文写作辅助工具</strong></p>
        <p>版本: 0.1.0 (UI 原型)</p>
        <p>基于私有文献知识库的论文写作辅助工具</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
  max-width: 600px;
}

.settings-page h2 {
  margin-bottom: 24px;
}

.settings-section {
  background: var(--bg-sidebar);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.settings-section h3 {
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item label {
  width: 120px;
  flex-shrink: 0;
  font-size: 14px;
}

.setting-item input,
.setting-item select {
  flex: 1;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
}

.setting-item input:focus,
.setting-item select:focus {
  outline: none;
  border-color: var(--primary);
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.status-badge.offline {
  background: rgba(239, 68, 68, 0.2);
  color: var(--error);
}

.status-badge.online {
  background: rgba(16, 163, 127, 0.2);
  color: var(--success);
}

.hint {
  font-size: 12px;
  color: var(--text-secondary);
}

.about-info {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.about-info strong {
  color: var(--text-primary);
}
</style>
```

**Step 2: 验证完整编译**

```bash
pnpm build
```

Expected: 编译成功

---

## Task 7: 最终验证

**Step 1: 启动开发服务器**

```bash
cd D:/同步/project/frontend-prototype
pnpm dev
```

**Step 2: 验证功能**

1. 访问 http://localhost:3000
2. 切换标签页（导入/对话/设置）
3. 在导入页测试导入动画
4. 在对话页发送消息，观察流式响应
5. 查看来源卡片展示

**Step 3: 提交代码**

```bash
cd D:/同步
git add project/frontend-prototype
git commit -m "feat: 添加前端 UI 原型展示"
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `package.json` | 项目配置 |
| `vite.config.ts` | Vite 配置 |
| `tsconfig.json` | TypeScript 配置 |
| `index.html` | 入口 HTML |
| `src/main.ts` | 应用入口 |
| `src/App.vue` | 根组件 |
| `src/style.css` | 全局样式 |
| `src/stores/mockStore.ts` | 模拟数据状态管理 |
| `src/components/layout/TabBar.vue` | 标签栏 |
| `src/components/layout/TabContent.vue` | 标签页容器 |
| `src/components/ingest/IngestPage.vue` | 导入页面 |
| `src/components/chat/ChatPage.vue` | 对话页面 |
| `src/components/chat/SessionList.vue` | 会话选择 |
| `src/components/chat/MessageList.vue` | 消息列表 |
| `src/components/chat/MessageItem.vue` | 消息项 |
| `src/components/chat/ChatInput.vue` | 输入框 |
| `src/components/settings/SettingsPage.vue` | 设置页面 |
