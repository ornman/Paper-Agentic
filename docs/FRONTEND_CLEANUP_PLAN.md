# 前端清理执行方案

## Context

经过 MVP 阶段快速迭代，前端积累了显著技术债：3 个超过 500 行的"上帝组件"（最大 1216 行）、类型定义散落在 service/store 文件中、API 层有 3 份重复的请求函数、ChatView 中 10+ 处 demo 模式散落判断。本方案旨在渐进式清理，每步完成后系统仍正常运行。

**当前数据**：24 个 Vue 组件（8,100 行），30 个 TS 文件（4,152 行），4 个 Store，9 个 Composable，5 个 Service 文件，2 条路由。

**最终保存位置**：`docs/FRONTEND_CLEANUP_PLAN.md`

---

## Phase 0: 死代码清除

**风险：低 | 预计变化：-15 行，删除 1 个文件**

### 0.1 删除 TopBar.vue 僵尸组件

TopBar.vue（12行）是 TopNavBar.vue 的纯透传包装器，零附加逻辑。

- **删除** `src/components/TopBar.vue`
- **改** `src/views/ChatView.vue`：
  - 将 `import TopBar` 改为 `import TopNavBar`
  - 将 `<TopBar ...>` 改为 `<TopNavBar title="论文助手" @new-chat="..." @open-history="..." />`

### 0.2 删除未使用的 SearchState 导出

- **改** `src/composables/use-library-search.ts`：删除 `export interface SearchState` 块（定义了但从未被导入）

### ⚠️ 审计纠误

以下两项经代码验证**不是死代码**，不要删：
- `conversation-api.ts` — 4 个函数全部被 ChatView.vue 导入使用
- `ImportProgressEvent` 类型 — 被 `library.ts` 的 `applyImportProgress` 函数引用

**验证**：`pnpm build` + 页面顶部导航正常、新建对话和历史按钮正常

---

## Phase 1: 类型系统集中化

**风险：低 | 预计变化：+60 行新文件，纯类型搬迁，无运行时影响**

### 1.1 创建 `src/types/paper.ts`

从 `src/services/library-api.ts` 搬出：
- `PaperItem`（论文数据）
- `ImportStartResult`（导入启动结果）
- `ImportStatus`（导入状态轮询）
- `ImportProgressEvent`（导入进度事件）

**需更新导入路径的文件**：
- `src/services/library-api.ts` — 改为从 `../types/paper` 导入
- `src/stores/library.ts` — 改为从 `../types/paper` 导入
- `src/composables/use-library-search.ts` — 同上
- `src/components/LibraryPanel.vue` — 同上
- `src/components/LibraryPaperCard.vue` — 同上
- `src/components/TrashPanel.vue` — 同上
- `src/demo/index.ts` — 同上

### 1.2 创建 `src/types/conversation.ts`

从 `src/services/conversation-api.ts` 搬出：
- `ConversationSession`（会话摘要）
- `ConversationMessage`（消息记录）

**需更新导入路径的文件**：
- `src/services/conversation-api.ts`
- `src/views/ChatView.vue`
- `src/components/HistoryPanel.vue`

### 1.3 创建 `src/types/message.ts`

从 `src/stores/conversation.ts` 搬出：
- `ConversationStatus`（状态枚举）
- `UserMessage`（用户消息）
- `AssistantMessage`（AI 消息）
- `ConversationRecord`（消息联合类型）

**需更新导入路径的文件**：
- `src/stores/conversation.ts`
- `src/components/AIMessage.vue`
- `src/components/UserMessage.vue`
- `src/components/MessageList.vue`
- `src/views/ChatView.vue`
- `src/demo/index.ts`

**验证**：`pnpm build` 通过，所有类型导入路径正确

---

## Phase 2: API 层去重

**风险：低-中 | 预计变化：-30 行**

### 2.1 统一 request 请求函数

当前 `request<T>(path, init)` 在 3 个文件中各有一份副本：
- `src/services/conversation-api.ts`
- `src/services/library-api.ts`
- `src/services/assistant-api.ts`

操作：
1. **改** `src/services/api-client.ts`：新增导出函数 `apiRequest<T>(pathname, init): Promise<T>`，复用已有的 `buildApiUrl`、`readJsonSafely`、`extractErrorMessage`
2. **改** 3 个 service 文件：删除各自的 `request<T>` 本地定义，改为 `import { apiRequest } from './api-client'`
3. `library-api.ts` 保留 `buildApiUrl` 导入（`createImportStream` 需要）

### 2.2 统一错误提取模式

当前 3 个文件的错误提取逻辑不一致（有的先取 `body.message`，有的先取 `body.detail`）。
统一到 `api-client.ts` 已有的 `extractErrorMessage` 函数。

**验证**：`pnpm build` + 手动测试导入文献、加载列表、发送消息、模拟网络错误

---

## Phase 3: 拆分 LibraryPanel（1216 行）

**风险：中 | 预计变化：+200 行新文件，LibraryPanel 净减约 200 行**

### 3.1 提取 ImportQueueList.vue — 消除模板重复

LibraryPanel 中导入队列的模板出现了**两次**（空库视图和页脚视图），HTML 几乎相同。

- **新建** `src/components/ImportQueueList.vue`
  - Props: `{ items: ImportQueueItem[], isEmptyLibrary: boolean }`
  - Emits: `{ retry: [idx: number], remove: [idx: number] }`
- **改** `LibraryPanel.vue`：两处重复块都替换为 `<ImportQueueList>`
- 搬迁相关 CSS（`.import-queue*` 规则）

### 3.2 提取 DeleteConfirmDialog.vue

删除确认弹窗有独立的状态机（visible/paperId/title/batchIds）和完整的 `<Teleport>` 模板。

- **新建** `src/components/DeleteConfirmDialog.vue`
  - Props: `{ visible, title, count, skipConfirm }`
  - Emits: `{ confirm, cancel, 'update:skipConfirm' }`
- **改** `LibraryPanel.vue`：`confirmDelete` reactive 状态改为 v-model 绑定到对话框
- 搬迁确认弹窗相关 CSS（`.confirm-*` 规则）

### 3.3 提取 useDropZone composable

拖拽上传逻辑完全自包含（dragActive ref + dragCounter + onDragEnter/onDragLeave/onDrop）。

- **新建** `src/composables/use-drop-zone.ts`
  - 参数：`(onDrop: (files: File[]) => void)`
  - 返回：`{ dragActive, onDragEnter, onDragLeave, onDrop }`
- **改** `LibraryPanel.vue`：替换内联拖拽逻辑

**验证**：拖拽上传 PDF、单个导入进度、批量导入队列、删除确认弹窗、回收站视图、文献搜索

---

## Phase 4: 拆分 ChatView（656 行）

**风险：中-高（最复杂的阶段）| 预计变化：+250 行新文件，ChatView 净减约 200 行**

### 4.0 修复 thinkingEnabled 状态重复（前置修复）

`ChatView.vue` 第 149 行的 `const thinkingEnabled = ref(false)` 与 `settingsStore.thinkingEnabled` 重复。

- **改** `ChatView.vue`：
  - 删除 `thinkingEnabled` ref
  - 模板中 `:thinking-enabled` 改为绑定 `settingsStore.thinkingEnabled`
  - `@toggle-thinking` 改为调用 `settingsStore.toggleThinking()`

### 4.1 提取 useCitationPreview composable

引用预览系统涉及 7 个 ref/function（previewVisible, previewSource, previewX/Y, hoverTimer, hideTimer, 各类 handler），约 65 行。

- **新建** `src/composables/use-citation-preview.ts`
  - 参数：`{ allSources, isWPSAvailable, openReader }`
  - 返回：`{ previewVisible, previewSource, previewX, previewY, handleCitationHover, handleCitationLeave, handleCitationClick, cancelHideTimer, startHideTimer, handlePreviewClick }`
- **改** `ChatView.vue`：替换为 composable 调用，模板绑定加 `citationPreview.` 前缀

### 4.2 提取 useSessionManager composable

会话管理涉及 sessions ref、sessionsLoading ref、以及 handleOpenHistory/switchToSession/handleDeleteSession 三个方法，约 120 行。其中 `switchToSession` 有 80 行复杂的消息映射逻辑。

- **新建** `src/composables/use-session-manager.ts`
  - 参数：`{ store, libraryStore, uiStore, demoActive }`
  - 返回：`{ sessions, sessionsLoading, handleOpenHistory, switchToSession, handleDeleteSession }`
- **改** `ChatView.vue`：替换为 composable 调用

### 4.3 提取 useAutoScroll composable

滚动到底部逻辑：messagesContainer ref + scrollToBottom 函数 + 2 个 watcher。

- **新建** `src/composables/use-auto-scroll.ts`
  - 参数：`{ trigger: () => any[] }`（watcher 的依赖）
  - 返回：`{ containerRef }`（template ref）

### 4.4 提取 useFileUpload composable

ChatView 中的 triggerFileUpload 创建隐藏 input 并点击，可复用。

- **新建** `src/composables/use-file-upload.ts`
  - 参数：`{ accept, onFiles }`
  - 返回：`{ triggerUpload }`
- **改** `ChatView.vue`：替换为 composable 调用

**验证**：发送消息、切换 thinking、悬浮引用、点击引用、切换会话、删除会话、上传 PDF、demo 模式

---

## Phase 5: AIMessage 清理

**风险：低 | 预计变化：+60 行新文件，AIMessage 净减 60 行（纯函数搬迁）**

### 5.1 提取引用渲染工具函数

AIMessage.vue 中的 `escapeHtml`、`renderParagraphWithCitations`、`renderInline` 三个函数是**纯函数**，无响应式依赖，应独立为工具函数。

- **新建** `src/utils/citation-renderer.ts`
  - 导出 `escapeHtml(str): string`
  - 导出 `renderInline(text): string`
  - 导出 `renderParagraphWithCitations(text, sources): string` — 将原来内部对 `numberedSources.value` 的引用改为参数传入
- **改** `AIMessage.vue`：从 `../utils/citation-renderer` 导入，删除内联定义

**验证**：AI 消息中引用标记渲染正确、悬浮/点击仍正常

---

## Phase 6: 路由懒加载 + 最终修整

**风险：低 | 预计变化：+10 行**

### 6.1 路由懒加载

- **改** `src/router/index.ts`：
  - `import ChatView from ...` → `const ChatView = () => import('../views/ChatView.vue')`
  - `import SettingsView from ...` → `const SettingsView = () => import('../views/SettingsView.vue')`

### 6.2 修复 WPS 轮询选择器 bug

`wps.ts` 第 274 行用 `document.querySelector('textarea.composer-input')` 查找输入框，但 InputBar.vue 第 33 行的实际 class 是 `composer-textarea`。这导致 WPS 自动填充功能静默失效。

- **改** `src/composables/wps.ts` 第 274 行：
  - `'textarea.composer-input'` → `'textarea.composer-textarea'`

### 6.3 修复 highlightText XSS 隐患

`use-library-search.ts` 的 `highlightText` 函数返回未转义的 HTML（`<mark>` 标签），被 `LibraryPaperCard.vue` 通过 `v-html` 使用。

- **改** `src/composables/use-library-search.ts`：
  - 在 `highlightText` 中先对 `text` 参数调用 `escapeHtml`，再注入 `<mark>` 标签
  - 导入 Phase 5 创建的 `escapeHtml`（或在本文件内添加同名工具函数）

**验证**：`pnpm build` 通过、访问 `/settings` 页面（验证懒加载）、WPS 环境下选区同步、搜索含特殊字符

---

## 全局文件变更清单

| 阶段 | 操作 | 文件路径 |
|------|------|---------|
| 0 | **删除** | `src/components/TopBar.vue` |
| 0 | 改 | `src/views/ChatView.vue` |
| 0 | 改 | `src/composables/use-library-search.ts` |
| 1 | **新建** | `src/types/paper.ts` |
| 1 | **新建** | `src/types/conversation.ts` |
| 1 | **新建** | `src/types/message.ts` |
| 1 | 改 | `src/services/library-api.ts`、`src/services/conversation-api.ts`、`src/stores/conversation.ts`、`src/stores/library.ts` |
| 1 | 改 | `src/composables/use-library-search.ts` |
| 1 | 改 | `src/components/LibraryPanel.vue`、`AIMessage.vue`、`MessageList.vue`、`UserMessage.vue`、`LibraryPaperCard.vue`、`TrashPanel.vue`、`HistoryPanel.vue` |
| 1 | 改 | `src/demo/index.ts` |
| 2 | 改 | `src/services/api-client.ts`、`conversation-api.ts`、`library-api.ts`、`assistant-api.ts` |
| 3 | **新建** | `src/components/ImportQueueList.vue`、`src/components/DeleteConfirmDialog.vue`、`src/composables/use-drop-zone.ts` |
| 3 | 改 | `src/components/LibraryPanel.vue` |
| 4 | **新建** | `src/composables/use-citation-preview.ts`、`use-session-manager.ts`、`use-auto-scroll.ts`、`use-file-upload.ts` |
| 4 | 改 | `src/views/ChatView.vue` |
| 5 | **新建** | `src/utils/citation-renderer.ts` |
| 5 | 改 | `src/components/AIMessage.vue` |
| 6 | 改 | `src/router/index.ts`、`src/composables/wps.ts`、`src/composables/use-library-search.ts` |

**新建 10 个文件，删除 1 个文件，修改约 25 个文件**

---

## 风险总览

| 阶段 | 风险 | 核心理由 |
|------|------|---------|
| 0 | 低 | 删除一个透传包装器 + 一个未使用的导出 |
| 1 | 低 | 纯类型搬迁，无运行时影响 |
| 2 | 低-中 | 修改 API 调用模式，需测试错误路径 |
| 3 | 中 | 模板重构，有视觉回归风险 |
| 4 | 中-高 | 最大重构，从 656 行编排器提取 4 个 composable |
| 5 | 低 | 纯函数提取，无响应式变更 |
| 6 | 低 | 标准模式 + bug 修复 |

## 执行顺序原理

- Phase 0-1 是前置条件：先清理死代码和统一类型，后续重构才不会带着包袱
- Phase 2 在 Phase 3-4 之前：composable 会导入清理后的 service 层
- Phase 3（LibraryPanel）比 Phase 4（ChatView）简单，先做建立信心
- Phase 5 依赖 Phase 4 完成后 citation-renderer 工具函数才稳定
- Phase 6 是收尾打磨，影响面最小

## 验证策略

每个 Phase 完成后执行：
1. `pnpm build` — 编译无错误
2. `pnpm dev` — 开发服务器启动正常
3. 手动冒烟测试：发送消息、引用交互、文献库操作、设置页面
4. Phase 4 完成后额外测试：demo 模式、WPS 轮询（如有环境）
