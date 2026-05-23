# 前端 Claude 风格重构计划 - 论文助手 V1

## 设计风格参考

Claude AI 官网风格：暖陶土色 + 干净编辑器布局 + 知识感

---

## 1. 颜色方案（CSS 变量）

### 1.1 主色调
```css
:root {
  /* 暖陶土色系 - Claude 风格核心 */
  --claude-primary: #CC6B49;       /* 主色：暖陶土 */
  --claude-primary-hover: #B55A3A; /* 悬停色 */
  --claude-primary-light: #F5E6E0; /* 浅色背景 */

  /* 中性色 */
  --claude-bg-main: #FAF9F7;       /* 主背景：米白 */
  --claude-bg-card: #FFFFFF;       /* 卡片背景：纯白 */
  --claude-bg-muted: #F5F4F2;      /* 次级背景 */
  --claude-border: #E8E6E3;        /* 边框色 */

  /* 文字色 */
  --claude-text-primary: #1A1915;   /* 主文字：深褐黑 */
  --claude-text-secondary: #6B6A64;/* 次要文字：暖灰 */
  --claude-text-muted: #9B9A94;     /* 弱化文字：浅灰 */

  /* 功能色 */
  --claude-success: #5B8C5A;       /* 成功：深绿 */
  --claude-warning: #C4863C;       /* 警告：深橙 */
  --claude-error: #C44C4C;         /* 错误：深红 */
  --claude-info: #4C7EC4;          /* 信息：深蓝 */

  /* 阴影 */
  --claude-shadow-sm: 0 1px 2px rgba(26, 25, 21, 0.05);
  --claude-shadow-md: 0 4px 12px rgba(26, 25, 21, 0.08);
  --claude-shadow-lg: 0 8px 24px rgba(26, 25, 21, 0.12);

  /* 圆角 */
  --claude-radius-sm: 6px;
  --claude-radius-md: 10px;
  --claude-radius-lg: 16px;
  --claude-radius-full: 9999px;

  /* 间距 */
  --claude-spacing-xs: 4px;
  --claude-spacing-sm: 8px;
  --claude-spacing-md: 16px;
  --claude-spacing-lg: 24px;
  --claude-spacing-xl: 32px;
}
```

---

## 2. 全局样式修改

### 2.1 文件：`src/style.css`

**完整替换为：**

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Georgia&display=swap');

:root {
  /* 暖陶土色系 - Claude 风格核心 */
  --claude-primary: #CC6B49;
  --claude-primary-hover: #B55A3A;
  --claude-primary-light: #F5E6E0;

  /* 中性色 */
  --claude-bg-main: #FAF9F7;
  --claude-bg-card: #FFFFFF;
  --claude-bg-muted: #F5F4F2;
  --claude-border: #E8E6E3;

  /* 文字色 */
  --claude-text-primary: #1A1915;
  --claude-text-secondary: #6B6A64;
  --claude-text-muted: #9B9A94;

  /* 功能色 */
  --claude-success: #5B8C5A;
  --claude-warning: #C4863C;
  --claude-error: #C44C4C;
  --claude-info: #4C7EC4;

  /* 阴影 */
  --claude-shadow-sm: 0 1px 2px rgba(26, 25, 21, 0.05);
  --claude-shadow-md: 0 4px 12px rgba(26, 25, 21, 0.08);
  --claude-shadow-lg: 0 8px 24px rgba(26, 25, 21, 0.12);

  /* 圆角 */
  --claude-radius-sm: 6px;
  --claude-radius-md: 10px;
  --claude-radius-lg: 16px;
  --claude-radius-full: 9999px;

  /* 间距 */
  --claude-spacing-xs: 4px;
  --claude-spacing-sm: 8px;
  --claude-spacing-md: 16px;
  --claude-spacing-lg: 24px;
  --claude-spacing-xl: 32px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: var(--claude-bg-main);
  color: var(--claude-text-primary);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

#app {
  min-height: 100vh;
}

/* 滚动条美化 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--claude-bg-muted);
}

::-webkit-scrollbar-thumb {
  background: var(--claude-border);
  border-radius: var(--claude-radius-full);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--claude-text-muted);
}

/* 按钮基础样式 */
button {
  font-family: inherit;
  cursor: pointer;
  border: none;
  background: none;
  transition: all 0.2s ease;
}

/* 输入框基础样式 */
input, textarea {
  font-family: inherit;
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  background: var(--claude-bg-card);
  color: var(--claude-text-primary);
  transition: border-color 0.2s ease;
}

input:focus, textarea:focus {
  outline: none;
  border-color: var(--claude-primary);
}
```

---

## 3. 组件修改清单

### 3.1 App.vue - 主布局

**文件：** `src/App.vue`

**修改重点：**
1. Tab 切换样式改为 Claude 风格
2. 整体背景色
3. 布局间距

```vue
<template>
  <div class="claude-app">
    <!-- 顶部 Tab 导航 -->
    <nav class="claude-nav">
      <div class="claude-nav-container">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="['claude-tab', { 'claude-tab-active': activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          <span class="claude-tab-icon">{{ tab.icon }}</span>
          <span class="claude-tab-label">{{ tab.label }}</span>
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
import ChatView from './views/ChatView.vue'
import LibraryView from './views/LibraryView.vue'

const activeTab = ref('chat')

const tabs = [
  { id: 'chat', icon: '💬', label: '对话' },
  { id: 'library', icon: '📚', label: '文献库' }
]
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
}

.claude-nav-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--claude-spacing-lg);
  display: flex;
  gap: var(--claude-spacing-sm);
}

.claude-tab {
  display: flex;
  align-items: center;
  gap: var(--claude-spacing-sm);
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  border-radius: var(--claude-radius-md);
  color: var(--claude-text-secondary);
  font-weight: 500;
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

.claude-main {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: var(--claude-spacing-lg);
}
</style>
```

---

### 3.2 ChatView.vue - 对话页面

**文件：** `src/views/ChatView.vue`

**修改重点：**
1. 布局改为左右分栏（左边历史记录，右边对话区）
2. 消息列表样式
3. 输入框区域样式

```vue
<template>
  <div class="claude-chat">
    <!-- 左侧边栏 - 对话历史 -->
    <aside class="claude-sidebar">
      <div class="claude-sidebar-header">
        <h2 class="claude-sidebar-title">对话历史</h2>
        <button class="claude-icon-btn" title="新对话">+</button>
      </div>
      <div class="claude-sidebar-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          :class="['claude-sidebar-item', { 'claude-sidebar-item-active': conv.id === currentId }]"
        >
          <div class="claude-sidebar-item-title">{{ conv.title }}</div>
          <div class="claude-sidebar-item-time">{{ conv.time }}</div>
        </div>
      </div>
    </aside>

    <!-- 右侧 - 对话区 -->
    <main class="claude-chat-main">
      <!-- 消息列表 -->
      <div class="claude-messages">
        <MessageList />
      </div>

      <!-- 输入区 -->
      <div class="claude-input-area">
        <textarea
          v-model="input"
          placeholder="输入问题..."
          class="claude-textarea"
          rows="3"
        />
        <div class="claude-input-actions">
          <span class="claude-input-hint">{{ input.length }} / 5000</span>
          <button class="claude-send-btn" :disabled="!input.trim()">
            发送
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.claude-chat {
  display: flex;
  gap: var(--claude-spacing-lg);
  height: calc(100vh - 120px);
}

.claude-sidebar {
  width: 260px;
  background: var(--claude-bg-card);
  border-radius: var(--claude-radius-lg);
  border: 1px solid var(--claude-border);
  display: flex;
  flex-direction: column;
}

.claude-sidebar-header {
  padding: var(--claude-spacing-md);
  border-bottom: 1px solid var(--claude-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.claude-sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--claude-text-primary);
}

.claude-icon-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--claude-radius-sm);
  background: var(--claude-bg-muted);
  color: var(--claude-text-primary);
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.claude-icon-btn:hover {
  background: var(--claude-primary-light);
  color: var(--claude-primary);
}

.claude-sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--claude-spacing-sm);
}

.claude-sidebar-item {
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  border-radius: var(--claude-radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
}

.claude-sidebar-item:hover {
  background: var(--claude-bg-muted);
}

.claude-sidebar-item-active {
  background: var(--claude-primary-light);
}

.claude-sidebar-item-title {
  font-size: 13px;
  color: var(--claude-text-primary);
  margin-bottom: 2px;
}

.claude-sidebar-item-time {
  font-size: 11px;
  color: var(--claude-text-muted);
}

.claude-chat-main {
  flex: 1;
  background: var(--claude-bg-card);
  border-radius: var(--claude-radius-lg);
  border: 1px solid var(--claude-border);
  display: flex;
  flex-direction: column;
}

.claude-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--claude-spacing-lg);
}

.claude-input-area {
  padding: var(--claude-spacing-md) var(--claude-spacing-lg);
  border-top: 1px solid var(--claude-border);
}

.claude-textarea {
  width: 100%;
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  padding: var(--claude-spacing-md);
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  font-family: inherit;
}

.claude-textarea:focus {
  border-color: var(--claude-primary);
  outline: none;
}

.claude-input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--claude-spacing-sm);
}

.claude-input-hint {
  font-size: 12px;
  color: var(--claude-text-muted);
}

.claude-send-btn {
  padding: var(--claude-spacing-sm) var(--claude-spacing-lg);
  background: var(--claude-primary);
  color: white;
  border-radius: var(--claude-radius-md);
  font-size: 14px;
  font-weight: 500;
}

.claude-send-btn:hover:not(:disabled) {
  background: var(--claude-primary-hover);
}

.claude-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
```

---

### 3.3 MessageList.vue - 消息列表

**文件：** `src/components/MessageList.vue`

**修改重点：**
1. 用户消息样式（右侧，暖色）
2. AI 消息样式（左侧，中性色）
3. 来源卡片样式

```vue
<template>
  <div class="claude-message-list">
    <div v-for="msg in messages" :key="msg.id" :class="['claude-message-row', msg.role]">
      <div class="claude-message-avatar">
        {{ msg.role === 'user' ? '👤' : '🤖' }}
      </div>
      <div class="claude-message-content">
        <div class="claude-message-text">{{ msg.content }}</div>
        <SourceCard v-if="msg.sources" :sources="msg.sources" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.claude-message-list {
  display: flex;
  flex-direction: column;
  gap: var(--claude-spacing-lg);
}

.claude-message-row {
  display: flex;
  gap: var(--claude-spacing-md);
}

.claude-message-row.user {
  flex-direction: row-reverse;
}

.claude-message-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--claude-radius-full);
  background: var(--claude-bg-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.claude-message-content {
  max-width: 70%;
}

.claude-message-text {
  padding: var(--claude-spacing-md) var(--claude-spacing-lg);
  border-radius: var(--claude-radius-lg);
  font-size: 14px;
  line-height: 1.6;
}

.claude-message-row.user .claude-message-text {
  background: var(--claude-primary);
  color: white;
  border-bottom-right-radius: var(--claude-radius-sm);
}

.claude-message-row.assistant .claude-message-text {
  background: var(--claude-bg-muted);
  color: var(--claude-text-primary);
  border-bottom-left-radius: var(--claude-radius-sm);
}
</style>
```

---

### 3.4 LibraryView.vue - 文献库页面

**文件：** `src/views/LibraryView.vue`

**修改重点：**
1. 搜索框样式
2. 论文卡片样式
3. 操作按钮样式

```vue
<template>
  <div class="claude-library">
    <!-- 顶部操作栏 -->
    <div class="claude-library-header">
      <h1 class="claude-library-title">文献库</h1>
      <div class="claude-library-actions">
        <input
          v-model="search"
          placeholder="搜索标题或作者..."
          class="claude-search-input"
        />
        <button class="claude-btn claude-btn-primary">
          上传 PDF
        </button>
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="claude-library-stats">
      <span>共 {{ papers.length }} 篇论文</span>
      <span>{{ totalChunks }} 个文本块</span>
    </div>

    <!-- 论文列表 -->
    <div class="claude-paper-list">
      <div v-for="paper in filteredPapers" :key="paper.id" class="claude-paper-card">
        <div class="claude-paper-title">{{ paper.title }}</div>
        <div class="claude-paper-meta">
          <span>{{ paper.authors }}</span>
          <span>{{ paper.chunkCount }} 块</span>
        </div>
        <div class="claude-paper-actions">
          <button class="claude-icon-btn">🗑️</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.claude-library {
  display: flex;
  flex-direction: column;
  gap: var(--claude-spacing-lg);
}

.claude-library-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.claude-library-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--claude-text-primary);
}

.claude-library-actions {
  display: flex;
  gap: var(--claude-spacing-md);
}

.claude-search-input {
  width: 280px;
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  font-size: 14px;
}

.claude-btn {
  padding: var(--claude-spacing-sm) var(--claude-spacing-lg);
  border-radius: var(--claude-radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.claude-btn-primary {
  background: var(--claude-primary);
  color: white;
}

.claude-btn-primary:hover {
  background: var(--claude-primary-hover);
}

.claude-library-stats {
  display: flex;
  gap: var(--claude-spacing-lg);
  font-size: 14px;
  color: var(--claude-text-secondary);
}

.claude-paper-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--claude-spacing-md);
}

.claude-paper-card {
  background: var(--claude-bg-card);
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  padding: var(--claude-spacing-md);
  transition: all 0.2s ease;
}

.claude-paper-card:hover {
  box-shadow: var(--claude-shadow-md);
  border-color: var(--claude-primary-light);
}

.claude-paper-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--claude-text-primary);
  margin-bottom: var(--claude-spacing-sm);
  line-height: 1.4;
}

.claude-paper-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--claude-text-secondary);
  margin-bottom: var(--claude-spacing-sm);
}

.claude-paper-actions {
  display: flex;
  gap: var(--claude-spacing-sm);
}
</style>
```

---

## 4. 实施顺序

1. **第一步**：修改 `src/style.css` - 添加 CSS 变量
2. **第二步**：修改 `src/App.vue` - Tab 导航样式
3. **第三步**：修改 `src/views/ChatView.vue` - 对话页面布局
4. **第四步**：修改 `src/components/MessageList.vue` - 消息样式
5. **第五步**：修改 `src/views/LibraryView.vue` - 文献库页面
6. **第六步**：运行 `npm run dev` 查看效果

---

## 5. 验证清单

- [ ] 整体背景为米白色 (#FAF9F7)
- [ ] 主按钮为暖陶土色 (#CC6B49)
- [ ] 文字为深褐黑色，清晰易读
- [ ] 圆角统一（6px / 10px / 16px）
- [ ] 阴影柔和自然
- [ ] 悬停有过渡动画
- [ ] 响应式布局正常

---

## 6. 备注

- 字体使用 Inter（数字/英文）+ 系统默认
- 所有颜色使用 CSS 变量，方便后续调整
- 保持简洁，避免过度装饰
- 确保文字对比度符合无障碍标准
