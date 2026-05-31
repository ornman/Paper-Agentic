# 前端技术全景说明

> 最后更新：2026-05-31 · 分支 `feat/pdf-reader-refactor`

---

## 一、技术栈

| 层面 | 技术 | 版本 |
|------|------|------|
| 框架 | Vue 3 (Composition API) | ^3.4.0 |
| 语言 | TypeScript (strict) | ^5.3.0 |
| 构建 | Vite | ^5.0.0 |
| 路由 | Vue Router | 4.6.4 |
| 状态管理 | Pinia | ^2.1.0 |
| PDF 渲染 | pdfjs-dist | ^5.7.284 |
| 模糊搜索 | Fuse.js | ^7.3.0 |
| 动画 | lottie-web | ^5.13.0 |
| 测试 | Vitest + Playwright | — |
| 包管理 | pnpm | — |

---

## 二、双目标构建架构

前端有**两个入口**，一套代码两种部署形态：

| 入口 | 文件 | 运行环境 | 构建产物 |
|------|------|----------|----------|
| **浏览器 SPA** | `app.html` | 浏览器直接访问 | 标准 ES Module |
| **WPS 插件** | `wps-plugin/taskpane.html` | WPS Office 内嵌浏览器 | IIFE 内联（避免 ES Module 兼容问题） |

构建时 `vite.config.ts` 的 `assembleWpsPlugin` 自定义插件会：

1. 把 `wps-plugin/ribbon.xml` + `main.js` 复制到 `dist/`
2. 把编译后的 JS/CSS 内联进 `dist/wps-plugin/taskpane.html`（IIFE 包裹）

开发模式下 Vite 代理 `/api` → `http://127.0.0.1:8000`，解决跨域。

---

## 三、目录结构总览

```
src/
├── main.ts                 # 应用入口
├── App.vue                 # 根组件（<RouterView>）
├── style.css               # 全局 CSS 设计系统（CSS Variables + light/dark 主题）
│
├── assets/                 # 静态资源
│   ├── animations/         #   Lottie 动画 JSON（easter-egg.json）
│   ├── icons/              #   11 个 SVG 图标
│   └── illustrations/      #   插图 SVG（research-paper.svg）
│
├── components/             # 15 个顶层组件 + 5 个 PDF 子组件
│   ├── TopBar.vue          #   → 委托 TopNavBar
│   ├── TopNavBar.vue       #   顶栏：汉堡菜单、Logo、新建对话、设置
│   ├── EmptyState.vue      #   空对话状态：问候语 + 12 条随机提示卡
│   ├── SidebarDrawer.vue   #   侧边抽屉：历史/文献库 双 Tab
│   ├── ConfigInitDialog.vue#   首次配置弹窗（13 个厂商预设）
│   ├── CitationPreview.vue #   引用悬停预览浮层
│   ├── AIMessage.vue       #   AI 消息：思考折叠、内容块、引用标记、操作栏
│   ├── UserMessage.vue     #   用户消息：编辑、复制、删除
│   ├── MessageList.vue     #   消息列表：渲染所有消息 + 错误横幅 + 打字动画
│   ├── HistoryPanel.vue    #   历史会话列表：搜索、日期分组、删除确认
│   ├── InputBar.vue        #   输入栏：多行文本、快捷操作、思考开关
│   ├── LibraryPanel.vue    #   文献库面板：拖拽上传、搜索、排序、批量操作
│   ├── LibraryPaperCard.vue#   文献卡片：标题高亮、关键词标签、操作按钮
│   ├── PdfReaderPanel.vue  #   PDF 全屏阅读器（核心大组件）
│   └── pdf-reader/         #   PDF 阅读器子组件
│       ├── PdfPage.vue     #     单页渲染：Canvas + TextLayer + AnnotationLayer + 高亮
│       ├── PdfToolbar.vue  #     工具栏：翻页、缩放、大纲、搜索、视图模式
│       ├── PdfSearchBar.vue#     搜索栏：输入、匹配计数、上下导航
│       ├── PdfOutline.vue  #     目录大纲面板
│       └── PdfOutlineItem.vue #  大纲递归树节点
│
├── composables/            # 10 个可组合函数
│   ├── logger.ts           #   日志：批量 + sendBeacon 发送到 127.0.0.1:3895
│   ├── use-theme.ts        #   主题：light/dark/system，localStorage 持久化
│   ├── use-library-search.ts # 文献搜索：Fuse.js 加权搜索 + 年份/作者筛选 + 排序
│   ├── use-pdfjs.ts        #   pdfjs-dist Worker 初始化
│   ├── use-pdf-renderer.ts #   虚拟渲染：3 种视图模式 + IntersectionObserver
│   ├── use-pdf-annotation.ts # PDF 注解层：内部链接跳转 + 外部链接安全处理
│   ├── use-pdf-search.ts   #   PDF 全文搜索：延迟文本提取 + 300ms 防抖 + 缓存
│   ├── use-pdf-keyboard.ts #   PDF 快捷键：Ctrl+F、方向键、+/-、Escape
│   ├── useSidebarResize.ts #   侧边栏拖拽调宽：240-480px，localStorage 持久化
│   └── wps.ts              #   WPS 集成：环境检测、选区同步、轮询
│
├── router/
│   └── index.ts            #   路由：/ → ChatView，/settings → SettingsView
│
├── services/               # API 层（5 个模块）
│   ├── api-client.ts       #   基础 HTTP 客户端：buildApiUrl、requestJson、postJson
│   ├── sse-client.ts       #   SSE 流式客户端：postAskStream（8 种事件类型）
│   ├── assistant-api.ts    #   WPS 上下文同步：选区、文档内容
│   ├── conversation-api.ts #   会话 CRUD：创建、列表、删除、获取消息
│   └── library-api.ts      #   文献管理：列表、删除、导入、状态轮询
│
├── stores/                 # 4 个 Pinia Store
│   ├── ui.ts               #   UI 状态：侧边栏、PDF 阅读器开关
│   ├── conversation.ts     #   对话核心：消息流、SSE 处理、会话管理（~348 行）
│   ├── library.ts          #   文献库：论文列表、导入队列、进度追踪（~472 行）
│   └── settings.ts         #   设置：API 配置、模型列表、功能开关
│
├── types/
│   ├── content.ts          #   ContentBlock 类型（段落/标题/代码/列表/表格等）
│   └── source.ts           #   SourceCard 类型（引用源信息）
│
├── utils/
│   └── markdown-inline.ts  #   行内 Markdown 渲染（加粗/斜体/代码）
│
├── views/
│   ├── ChatView.vue        #   主视图：编排所有交互逻辑（~620 行）
│   └── SettingsView.vue    #   设置页：模型配置、功能开关、主题切换
│
└── demo/
    └── index.ts            #   Demo 模式：模拟数据 + 模拟流式响应
```

---

## 四、组件详细说明

### 4.1 顶层组件

| 组件 | 文件 | 职责 | Props | Emits |
|------|------|------|-------|-------|
| **TopBar** | `TopBar.vue` | 薄包装层，委托给 TopNavBar | 无 | `new-chat`, `open-history` |
| **TopNavBar** | `TopNavBar.vue` | 粘性顶栏：汉堡菜单、Logo、标题、新建对话按钮、设置链接 | `title: string` | `open-history`, `new-chat` |
| **EmptyState** | `EmptyState.vue` | 对话为空时显示：问候语 + 随机按钮 + 6 张提示卡（从 12 条池中随机选取） | 无 | `select-prompt(text)` |
| **SidebarDrawer** | `SidebarDrawer.vue` | Teleport 左侧抽屉，双 Tab（历史/文献库），具名插槽 | `visible`, `activeTab` | `close`, `update:activeTab` |
| **ConfigInitDialog** | `ConfigInitDialog.vue` | Teleport 模态框，首次 LLM/Embedding 配置，13 个厂商预设 | `visible` | `close`, `saved` |
| **CitationPreview** | `CitationPreview.vue` | Teleport 悬浮提示，引用源详情（标题/页码/内容），视口边界夹紧 | `visible`, `source`, `x`, `y` | `preview-enter`, `preview-leave`, `preview-click` |
| **AIMessage** | `AIMessage.vue` | AI 消息渲染：可折叠思考区（带计时）、阶段状态指示器、结构化内容块、流式光标、行内引用标记 `[N]`、引用徽章、操作栏（复制/重试/停止/追问/删除） | `message`, `isStreaming`, `phaseMessage?` | `citation-hover/leave/click`, `regenerate`, `stop`, `delete`, `follow-up` |
| **UserMessage** | `UserMessage.vue` | 用户消息气泡：行内编辑、复制、删除 | `message` | `resubmit(id, newText)`, `delete(id)` |
| **MessageList** | `MessageList.vue` | 渲染完整消息列表（User + AI），错误横幅 + 重试 + 打字动画 | `messages`, `status`, `errorMessage?`, `phaseMessage?` | `citation-hover/leave/click`, `retry`, `regenerate`, `stop`, `delete-message`, `resubmit-message`, `follow-up` |
| **HistoryPanel** | `HistoryPanel.vue` | 会话列表：搜索过滤、日期格式化、删除确认 | `sessions`, `loading`, `activeSessionId` | `select(id)`, `delete(id)` |
| **InputBar** | `InputBar.vue` | 多行输入栏：已选论文徽章（悬停提示）、自适应高度文本区、发送/停止/展开按钮、快捷操作栏（引用文献/导入PDF/深度思考开关） | `isBusy`, `selectedPaperCount`, `thinkingEnabled`, `selectedPaperNames?` | `send`, `stop`, `upload-pdf`, `toggle-papers`, `clear-papers`, `toggle-thinking` |
| **LibraryPanel** | `LibraryPanel.vue` | 文献库面板：拖拽上传、Fuse.js 搜索 + 年份/作者筛选 + 排序、全选（半选态）、批量删除确认、导入队列进度追踪 + 重试 | `papers`, `loading`, `error`, `selectedIds` | `toggle`, `upload`, `remove`, `select-all`, `retry` |
| **LibraryPaperCard** | `LibraryPaperCard.vue` | 文献卡片：复选框、标题（高亮）、元数据（作者/年份/页数/分块数）、关键词标签、悬停操作（预览/删除/重试） | `paper`, `selected`, `highlightFn?`, `maxKeywords?` | `toggle`, `remove`, `preview`, `retry` |
| **PdfReaderPanel** | `PdfReaderPanel.vue` | 全屏 PDF 阅读器：pdfjs-dist 加载、大纲/TOC、搜索、注解、3 种视图模式、IntersectionObserver 虚拟渲染 | `visible`, `paperId`, `targetPage?`, `highlightText?`, `demoMode?` | `close` |

### 4.2 PDF 阅读器子组件

| 组件 | 文件 | 职责 | Props | Emits |
|------|------|------|-------|-------|
| **PdfPage** | `pdf-reader/PdfPage.vue` | 单页渲染：Canvas（DPR 自适应）+ TextLayer（文本选择）+ AnnotationLayer（可点击链接）+ 高亮矩形（搜索/引用） | `pdfDoc`, `pageNumber`, `scale`, `containerWidth`, `highlightText?`, `highlightRects?`, `currentHighlightIndex?`, `searchMatches?`, `annotationAdapter?` | `page-height` |
| **PdfToolbar** | `pdf-reader/PdfToolbar.vue` | 工具栏：翻页 + 跳页输入、缩放（含百分比显示）、大纲开关、搜索开关、3 个视图模式按钮。内嵌 PdfSearchBar | `title`, `currentPage`, `totalPages`, `scale`, `outlineOpen`, `showOutlineButton`, `searchOpen`, `searchQuery`, `searchMatchCount`, `searchCurrentIndex`, `viewMode` | 13 个事件 |
| **PdfSearchBar** | `pdf-reader/PdfSearchBar.vue` | 行内搜索输入：匹配计数、上/下导航、关闭 | `query`, `matchCount`, `currentMatchIndex` | `search`, `next`, `prev`, `close` |
| **PdfOutline** | `pdf-reader/PdfOutline.vue` | 滑入目录面板：大纲树、当前页高亮 | `open`, `items: OutlineItem[]`, `currentPage` | `close`, `navigate(pageNumber)` |
| **PdfOutlineItem** | `pdf-reader/PdfOutlineItem.vue` | 大纲递归树节点：按深度缩进、当前页高亮 | `item: OutlineItem`, `depth`, `currentPage` | `navigate(pageNumber)` |

### 4.3 页面视图

| 视图 | 文件 | 职责 |
|------|------|------|
| **ChatView** | `views/ChatView.vue` | 主应用视图（~620 行）。编排：消息发送、会话管理（创建/列表/删除/切换）、WPS 轮询集成、Demo 模式自动激活（探测后端不可达则激活）、引用悬停预览（300ms 延迟）、PDF 阅读器面板、配置弹窗。快捷键：Ctrl+K 打开历史、Ctrl+N 新建对话 |
| **SettingsView** | `views/SettingsView.vue` | 设置页。分区：模型配置（重新初始化按钮、深度思考开关）、对话行为（反思/RAG 开关）、主题（system/light/dark 切换器）、关于区（技术标签 + 彩蛋——连点 Logo 5 次触发 Lottie 动画） |

---

## 五、Composable 详细说明

| Composable | 文件 | 管理的状态 | 是否调用 API |
|---|---|---|---|
| **useTheme** | `use-theme.ts` | 主题模式（`light`/`dark`/`system`），localStorage 持久化，`matchMedia` 监听系统偏好，模块级初始化防 FOUC | 否 |
| **useLibrarySearch** | `use-library-search.ts` | Fuse.js 客户端搜索（标题 50%、作者 30%、关键词 20%），年份/作者筛选下拉、排序模式（相关性/时间/年份/标题）、关键词重叠相似度查找、正则安全高亮函数 | 否 |
| **usePdfjs** | `use-pdfjs.ts` | pdfjs-dist Worker 初始化（开发用 import.meta.url，WPS IIFE 用空 Worker），设置 `globalThis.pdfjsLib` 兼容 pdf_viewer.mjs | 否 |
| **usePdfRenderer** | `use-pdf-renderer.ts` | 虚拟页面渲染，3 种视图模式：`single`（单页）、`double`（双页从奇数页开始）、`continuous`（IntersectionObserver + ±2 页缓冲区）。管理 `currentPage`、`totalPages`、`pageHeights`、`pagesToRender`、`visiblePages` | 否 |
| **usePdfAnnotation** | `use-pdf-annotation.ts` | pdfjs AnnotationLayer 渲染可点击链接注解。提供 duck-typed `LinkService`：支持内部目标导航（解析命名目标到页码）和外部链接安全处理 | 否 |
| **usePdfSearch** | `use-pdf-search.ts` | PDF 全文搜索：延迟文本提取（按页缓存）、300ms 防抖搜索、跟踪匹配位置（pageIndex, charStart, charEnd）、上/下导航 | 否 |
| **usePdfKeyboard** | `use-pdf-keyboard.ts` | PDF 阅读器快捷键：Ctrl+F（搜索）、ArrowUp/k（上一页）、ArrowDown/j（下一页）、+/-（缩放）、Ctrl+Home/End（首尾页）、Escape（关闭搜索或面板）。仅在非输入框聚焦时激活 | 否 |
| **useSidebarResize** | `useSidebarResize.ts` | 侧边栏拖拽调宽：最小 240px、最大 480px、默认 320px，localStorage 持久化 | 否 |
| **useWPSDetection** | `wps.ts` | 检测 WPS Office API 可用性（`window.wps.WpsApplication()`） | 否 |
| **useWPSSelection** | `wps.ts` | 读取 WPS 选区（Range.Text with offset，回退到 Selection.Text）和文档内容 | 否 |
| **useWPSSelectionChange** | `wps.ts` | 事件驱动选区监控（300ms 防抖）+ 2s 重绑定 watch 保证健壮性 | 否 |
| **useWPSPolling** | `wps.ts` | 3s 间隔轮询保底：选区同步（自动填充输入框）+ 文档内容同步（10s 节流） | 是 → `PUT /api/v1/assistant/selection`、`PUT /api/v1/assistant/written-context` |

---

## 六、Pinia Store 详细说明

### 6.1 `ui` Store（`stores/ui.ts`）

**职责**：全局 UI 开关状态

**State**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `sidebarOpen` | `boolean` | 侧边栏是否打开 |
| `sidebarTab` | `'history' \| 'library'` | 当前激活的 Tab |
| `readerOpen` | `boolean` | PDF 阅读器是否打开 |
| `readerPaperId` | `string \| null` | 当前展示的论文 ID |
| `readerTargetPage` | `number \| undefined` | 跳转目标页码 |
| `readerHighlightText` | `string \| null` | PDF 中要高亮的文本 |

**Actions**：`openSidebar(tab?)`, `closeSidebar()`, `openReader(paperId, page?, highlightText?)`, `closeReader()`

### 6.2 `conversation` Store（`stores/conversation.ts`，~348 行）

**职责**：对话核心——消息流、SSE 处理、会话管理

**State**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `ConversationStatus` | `'idle' \| 'requesting' \| 'thinking' \| 'streaming' \| 'done' \| 'error'` |
| `errorMessage` | `string \| null` | 错误信息 |
| `messages` | `ConversationRecord[]` | `UserMessage \| AssistantMessage` 数组 |
| `sessionId` | `string` | UUID 会话 ID |
| `activeAssistantId` | `string \| null` | 当前流式传输的 AI 消息 ID |
| `abortController` | `AbortController \| null` | 用于取消 SSE |
| `phaseMessage` | `string` | 当前处理阶段文本 |

**关键类型**：
- `UserMessage` — `{ id, role: 'user', content, createdAt }`
- `AssistantMessage` — `{ id, role: 'assistant', createdAt, thinking, thinkingTimeMs, blocks: ContentBlock[], sources: SourceCard[], streamingText }`
- `ConversationRecord = UserMessage | AssistantMessage`

**Actions**：
| Action | 说明 |
|--------|------|
| `reset()` | 重置所有状态 |
| `sendPrompt(payload)` | 发送消息：Demo 模式走 mock，真实模式走 SSE `postAskStream`。处理 8 种 SSE 事件：`status`、`thinking`、`delta`、`block`、`sources`、`done`、`error`、`message`（兼容回退） |
| `abortStreaming()` | 中断当前流式传输 |
| `deleteMessagePair(id)` | 删除用户消息及后续 AI 回答 |
| `deleteMessage(id)` | 删除单条消息 |
| `regenerateAfterUser(id)` | 在指定用户消息后重新生成 |
| `resubmitMessage(id, newText)` | 编辑用户消息并重新提交 |

### 6.3 `library` Store（`stores/library.ts`，~472 行）

**职责**：文献库管理——论文列表、导入管道

**State**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `papers` | `PaperItem[]` | 论文列表 |
| `loading` | `boolean` | 加载中 |
| `error` | `string \| null` | 错误信息 |
| `selectedPaperIds` | `string[]` | 已选论文 ID 列表 |
| `importing` | `boolean` | 是否正在导入 |
| `importFileName` | `string` | 当前导入文件名 |
| `importStep` | `string` | 当前导入阶段 |
| `importPercent` | `number` | 导入进度百分比 |
| `importError` | `string \| null` | 导入错误信息 |
| `importQueue` | `ImportQueueItem[]` | 导入队列，持久化到 localStorage |

**导入管道**：轮询（1s 间隔，最多连续 30 次失败）追踪进度。7 个阶段：`starting` → `transforming` → `cleaning` → `vlm_enriching` → `chunking` → `embedding` → `indexing`。导入队列持久化到 localStorage，页面刷新后自动恢复。

**Actions**：
| Action | 说明 |
|--------|------|
| `loadPapers()` | 加载论文列表 |
| `resumeImports()` | 恢复未完成的导入 |
| `removePaper(id)` | 删除论文 |
| `togglePaperSelection(id)` | 切换论文选中状态 |
| `setSelectedPaperIds(ids)` | 设置选中论文 |
| `clearSelectedPapers()` | 清空选中 |
| `importFile(file)` / `importFiles(files)` | 开始导入 |
| `monitorImportStatus(taskId, queueIdx?)` | 轮询导入进度 |
| `retryQueueItem(index)` | 重试导入队列项 |
| `clearImportError/Queue()` | 清理导入状态 |

### 6.4 `settings` Store（`stores/settings.ts`）

**职责**：用户设置，全部通过 `watch` 持久化到 localStorage

**State**：
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `apiUrl` | `string` | — | API 地址 |
| `apiKey` | `string` | — | API Key |
| `models` | `string[]` | `[]` | 可用模型列表 |
| `selectedModel` | `string` | — | 当前选中模型 |
| `thinkingEnabled` | `boolean` | `true` | 深度思考开关 |
| `reflectionEnabled` | `boolean` | `false` | 反思模式开关 |
| `ragEnabled` | `boolean` | `true` | RAG 检索开关 |
| `fontSize` | `number` | `14` | 字体大小 |
| `backendConfigured` | `boolean` | `false` | 后端是否已配置 |
| `configLoading` | `boolean` | `false` | 配置加载中 |

**Actions**：
| Action | 说明 |
|--------|------|
| `fetchModels()` | 从 LLM API 获取模型列表（OpenAI 兼容 `/v1/models`） |
| `fetchBackendConfig()` | `GET /api/v1/config/env` |
| `toggleThinking()` | 切换深度思考 |
| `clearCache()` | 清理缓存 |
| `exportData()` | 导出数据 |
| `estimateStorageUsage()` | 估算存储占用 |

---

## 七、API 层详细说明

### 7.1 `api-client.ts` — 基础 HTTP 客户端

| 导出 | 说明 |
|------|------|
| `ApiClientError` | 错误类，带 `statusCode` 字段 |
| `buildApiUrl(pathname)` | 解析 base URL：检查 `VITE_API_BASE_URL` 环境变量，开发服务器（3893 端口）用相对路径（Vite 代理），其他默认 `http://127.0.0.1:8000` |
| `requestJson<T>(pathname, init?)` | 通用 JSON 请求，返回 `ApiResponseEnvelope<T>`（`{ code, data, message }`） |
| `requestJsonData<T>(pathname, init?)` | 便捷包装，自动解包 envelope |
| `fetchHealthCheck()` | `GET /api/v1/health` |
| `postJson<T>(pathname, body)` | POST JSON 请求 |

### 7.2 `sse-client.ts` — SSE 流式客户端

| 导出 | 说明 |
|------|------|
| `AskRequestPayload` | 请求类型：`{ session_id, prompt, selection?, draft?, paper_ids?, enable_rag?, model?, thinking?, reflection? }` |
| `AskStreamHandlers` | 回调类型：每个 SSE 事件一个回调 |
| `postAskStream(payload, handlers, signal?)` | 流式请求 `POST /api/v1/query`，`Accept: text/event-stream`，120s 超时。解析 8 种事件：`status`、`thinking`、`delta`、`block`、`sources`、`done`、`error`、`message`（兼容回退） |

### 7.3 `assistant-api.ts` — WPS 上下文同步

| 函数 | 方法 | 路径 |
|------|------|------|
| `updateWrittenContext(sessionId, content)` | PUT | `/api/v1/assistant/written-context` |
| `getWrittenContext(sessionId)` | GET | `/api/v1/assistant/written-context/{id}` |
| `updateSelection(sessionId, selection, start?, end?)` | PUT | `/api/v1/assistant/selection` |
| `getSelection(sessionId)` | GET | `/api/v1/assistant/selection/{id}` |

### 7.4 `conversation-api.ts` — 会话 CRUD

| 函数 | 方法 | 路径 |
|------|------|------|
| `listSessions()` | GET | `/api/v1/conversations` |
| `createSession()` | POST | `/api/v1/conversations` |
| `deleteSession(sessionId)` | DELETE | `/api/v1/conversations/{id}` |
| `getMessages(sessionId, limit=50)` | GET | `/api/v1/conversations/{id}/messages?limit=50` |

### 7.5 `library-api.ts` — 文献库管理

| 函数 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `fetchPapers()` | GET | `/api/v1/library/items` | 映射 `library_item_id` → `paper_id` |
| `deletePaper(paperId)` | DELETE | `/api/v1/library/items/{id}` | |
| `retryImport(paperId)` | POST | `/api/v1/library/items/{id}/retry` | |
| `startImport(file)` | POST | `/api/v1/import/start` | FormData，检测重复状态 |
| `fetchImportStatus(taskId)` | GET | `/api/v1/import/status/{id}` | |
| `createImportStream(taskId)` | EventSource | `/api/v1/import/stream/{id}` | SSE 流（已定义未使用） |
| `buildPaperOpenUrl(paperId)` | — | `/api/v1/papers/{id}/open` | 构建 PDF 代理 URL |

---

## 八、TypeScript 类型

### 8.1 `types/content.ts` — 内容块

```typescript
interface ContentBlock {
  type: 'paragraph' | 'heading' | 'code' | 'list' | 'blockquote' | 'table' | 'divider' | string
  text?: string
  level?: number           // heading 级别
  language?: string         // 代码语言
  items?: string[]          // 列表项
  ordered?: boolean         // 有序列表
  code?: string             // 代码内容
  headers?: string[]        // 表头
  rows?: string[][]         // 表行
}
```

### 8.2 `types/source.ts` — 引用源

```typescript
interface SourceCard {
  id: string
  paper_id?: string
  title: string
  page?: number
  section?: string
  file_path?: string
  local_path?: string
  content?: string
  import_time?: string
}
```

### 8.3 其他关键类型（定义在各模块内部）

| 类型 | 所在文件 | 说明 |
|------|----------|------|
| `ApiClientError` | `api-client.ts` | 带 `statusCode` 的错误类 |
| `ApiResponseEnvelope<T>` | `api-client.ts` | `{ code, data, message }` |
| `AskRequestPayload` | `sse-client.ts` | SSE 查询请求体 |
| `AskStreamHandlers` | `sse-client.ts` | SSE 事件回调集合 |
| `PaperItem` | `library-api.ts` | 论文元数据（17 个字段） |
| `ImportStartResult` | `library-api.ts` | 导入启动结果 |
| `ImportStatus` | `library-api.ts` | 导入状态 |
| `ImportProgressEvent` | `library-api.ts` | 导入进度事件 |
| `ConversationSession` | `conversation-api.ts` | 会话摘要 |
| `ConversationMessage` | `conversation-api.ts` | 会话消息 |
| `BackendConfig` | `settings.ts` | `{ data, configured: { llm, embedding, mineru } }` |
| `ViewMode` | `use-pdf-renderer.ts` | `'single' \| 'double' \| 'continuous'` |
| `SearchMatch` | `use-pdf-search.ts` | `{ pageIndex, charStart, charEnd, text }` |
| `SelectionInfo` | `wps.ts` | `{ text, start, end, source }` |
| `AnnotationAdapter` | `use-pdf-annotation.ts` | 注解适配器 |
| `OutlineItem` | `PdfOutline.vue` | `{ title, dest, items, pageNumber? }` |
| `HighlightRect` | `PdfPage.vue` | 高亮矩形 |
| `SearchMatchOnPage` | `PdfPage.vue` | 页面搜索匹配 |
| `ThemeMode` | `use-theme.ts` | `'light' \| 'dark' \| 'system'` |
| `SidebarTab` | `ui.ts` | `'history' \| 'library'` |
| `ImportQueueItem` | `library.ts` | 导入队列项 |
| `ConversationStatus` | `conversation.ts` | `'idle' \| 'requesting' \| 'thinking' \| 'streaming' \| 'done' \| 'error'` |
| `UserMessage` | `conversation.ts` | 用户消息 |
| `AssistantMessage` | `conversation.ts` | AI 消息 |
| `ConversationRecord` | `conversation.ts` | `UserMessage \| AssistantMessage` |

---

## 九、文件联动关系

### 9.1 数据流向：用户提问 → AI 回答

```
用户输入
  ↓
InputBar.vue (send event)
  ↓
ChatView.vue (handleSend)
  ↓
conversation store → sendPrompt()
  ├── [Demo 模式] → demo/index.ts 模拟流式
  └── [真实模式] → sse-client.ts → POST /api/v1/query
                     ↓ SSE 事件流
                     status / thinking / delta / block / sources / done / error
  ↓
conversation store → 更新 messages[]
  ↓
MessageList.vue → 遍历渲染
  ├── UserMessage.vue  (role === 'user')
  └── AIMessage.vue    (role === 'assistant')
       ├── 思考折叠区
       ├── 内容块渲染 (ContentBlock[])
       ├── 引用标记 [N] → CitationPreview.vue (悬停预览)
       └── 操作栏（复制/重试/删除/追问）
```

### 9.2 文献导入流程

```
拖拽/选择文件
  ↓
LibraryPanel.vue (upload event)
  ↓
library store → importFile(file) / importFiles(files)
  ↓
library-api.ts → POST /api/v1/import/start (FormData)
  ↓ 返回 taskId
library store → monitorImportStatus(taskId)
  ↓ 1s 轮询 GET /api/v1/import/status/{id}
  ↓ 阶段：starting → transforming → cleaning → vlm_enriching → chunking → embedding → indexing
  ↓
导入完成 → 自动刷新 papers 列表
  ↓
导入队列持久化到 localStorage（防刷新丢失）
```

### 9.3 PDF 阅读器联动

```
用户点击引用源 → CitationPreview.vue (preview-click event)
  ↓
ui store → openReader(paperId, page, highlightText)
  ↓
ChatView.vue → PdfReaderPanel.vue (visible / paperId / targetPage)
  ↓
PdfReaderPanel.vue 内部编排：
  ├── use-pdfjs.ts          → 初始化 Worker
  ├── use-pdf-renderer.ts   → 视图模式 + 虚拟渲染
  │     └── IntersectionObserver → 可见页 ±2 缓冲
  ├── use-pdf-search.ts     → 全文搜索 + 高亮
  ├── use-pdf-annotation.ts → 链接注解（内部跳转 + 外部安全）
  ├── use-pdf-keyboard.ts   → 快捷键
  ├── PdfToolbar.vue        → 工具栏（翻页/缩放/大纲/搜索/视图）
  ├── PdfOutline.vue        → 大纲导航
  └── PdfPage.vue           → 单页渲染（Canvas + TextLayer + AnnotationLayer）
```

### 9.4 WPS 集成数据流

```
WPS Office 环境
  ↓
wps.ts → useWPSDetection() → 检测 window.wps API
  ↓
  ├── useWPSSelection()       → 获取选区文本和文档内容
  ├── useWPSSelectionChange() → 监听选区变化（300ms 防抖）
  └── useWPSPolling()         → 3s 轮询保底
       ↓
  assistant-api.ts → PUT /api/v1/assistant/selection
                   → PUT /api/v1/assistant/written-context
```

### 9.5 Store 之间的联动

```
ui store ←──── ChatView.vue ────→ conversation store
  │                                     │
  │ openReader()                        │ sendPrompt()
  │ closeReader()                       │ abortStreaming()
  │ openSidebar()                       │ deleteMessagePair()
  │ closeSidebar()                      │ regenerateAfterUser()
  │                                     │
  └──── ChatView.vue ────→ library store
                              │
                              │ loadPapers()
                              │ importFile()
                              │ togglePaperSelection()
                              │
  settings store ←── ChatView.vue / SettingsView.vue
     │
     │ fetchModels() → 从 LLM API 获取模型列表
     │ fetchBackendConfig() → GET /api/v1/config/env
     │ toggleThinking() → 开关深度思考
     │
     └── conversation store 读取 selectedModel、thinkingEnabled、ragEnabled
```

---

## 十、完整功能清单

### 10.1 对话系统

| 功能 | 说明 |
|------|------|
| 新建对话 | 生成 UUID 会话 ID，重置消息列表 |
| 发送消息 | 支持纯文本 + 选中文献上下文 |
| 流式响应 | SSE 实时接收，支持中断（AbortController） |
| 深度思考 | 可开关，AI 先思考再回答，带计时显示 |
| 内容块渲染 | 段落、标题、代码块（带语言标签）、有序/无序列表、表格、引用、分割线 |
| 引用标记 | AI 回答自动插入 `[N]` 标记，点击可跳转到 PDF 原文 |
| 引用预览 | 悬停 `[N]` 显示浮层（论文名/页码/内容片段） |
| 重试 | 可重新生成 AI 回答 |
| 编辑重发 | 可编辑已发送的用户消息并重新提交 |
| 删除消息 | 删除用户消息会同时删除后续 AI 回答 |
| 追问 | 基于当前回答快速发送追问 |
| 会话历史 | 侧边栏列表，支持搜索过滤、按日期分组 |
| 会话切换 | 点击历史项切换会话，加载对应消息 |
| 会话删除 | 带确认对话框 |
| 快捷键 | `Ctrl+K` 打开历史，`Ctrl+N` 新建对话 |

### 10.2 文献库

| 功能 | 说明 |
|------|------|
| PDF 上传 | 拖拽或点击上传，支持多文件批量导入 |
| 导入进度 | 实时轮询后端状态（7 个阶段），带进度条和步骤名称 |
| 导入队列 | 持久化到 localStorage，页面刷新后自动恢复 |
| 导入重试 | 失败项可单独重试 |
| 论文列表 | 显示标题、作者、年份、页数、分块数、关键词标签 |
| 模糊搜索 | Fuse.js 加权搜索（标题 50%、作者 30%、关键词 20%） |
| 筛选 | 年份下拉、作者下拉（自动提取选项） |
| 排序 | 相关性 / 导入时间 / 年份 / 标题 |
| 搜索高亮 | 匹配词在标题中高亮显示 |
| 全选/批量操作 | 全选 + 批量删除（带确认对话框） |
| 单选 | 勾选论文用于对话时引用 |
| 预览 | 悬停卡片可快速预览 |
| 删除 | 单个或批量删除，带确认 |

### 10.3 PDF 阅读器

| 功能 | 说明 |
|------|------|
| PDF 渲染 | pdfjs-dist Canvas 渲染，DPR 自适应 |
| 文本选择 | TextLayer 支持鼠标选择复制 |
| 链接注解 | AnnotationLayer 处理内部跳转和外部链接 |
| 目录导航 | 从 PDF 提取大纲树，点击跳转对应页 |
| 翻页 | 上一页/下一页 + 跳转到指定页 |
| 缩放 | 放大/缩小 + 百分比显示 |
| 全文搜索 | 懒加载提取各页文本，300ms 防抖搜索 |
| 搜索高亮 | 在 PDF 页面上绘制高亮矩形（基于文本坐标变换计算） |
| 搜索导航 | 上一个/下一个匹配项，显示 N/M 计数 |
| 视图模式 | 单页 / 双页 / 连续滚动 |
| 虚拟渲染 | IntersectionObserver，可见页 ±2 缓冲区 |
| 引用跳转 | 从对话引用直接跳转到 PDF 指定页并高亮文本 |
| 快捷键 | Ctrl+F 搜索、方向键翻页、+/- 缩放、Escape 关闭 |

### 10.4 设置

| 功能 | 说明 |
|------|------|
| 模型配置 | 显示当前配置状态，重新初始化按钮 |
| 深度思考 | 全局开关 |
| RAG 检索 | 开关是否使用 RAG |
| 反思模式 | 开关是否启用反思 |
| 主题 | 系统跟随 / 浅色 / 深色，CSS Variables 切换 |
| 彩蛋 | 连点 Logo 5 次触发 Lottie 动画 |

### 10.5 WPS 集成

| 功能 | 说明 |
|------|------|
| 环境检测 | 检测是否运行在 WPS 内 |
| 选区同步 | WPS 中选中文本自动填充到输入框 |
| 文档同步 | 定期同步当前文档内容到后端 |
| 打开 PDF | 调用 WPS API 在外部打开 PDF |

### 10.6 Demo 模式

| 触发条件 | 行为 |
|----------|------|
| URL 带 `?demo` 参数 | 激活 Demo 模式 |
| 后端不可达 | 自动激活 Demo 模式 |
| — | 提供 5 篇模拟论文、2 个模拟会话、模拟流式响应 |

### 10.7 首次配置

| 功能 | 说明 |
|------|------|
| 配置弹窗 | 首次使用弹出，配置 LLM 和 Embedding API |
| 厂商预设 | 13 个：DeepSeek、GLM、SiliconFlow、Kimi、豆包、百度、阿里、讯飞、OpenAI、Groq、Anthropic、Gemini、自定义 |
| 保存到后端 | `POST /api/v1/config/env` 写入 `.env` |

---

## 十一、API 接口汇总

| 方法 | 路径 | 用途 | 调用方 |
|------|------|------|--------|
| GET | `/api/v1/health` | 健康检查 | ChatView（Demo 检测） |
| GET | `/api/v1/config/env` | 获取后端配置 | settings store |
| POST | `/api/v1/config/env` | 保存配置 | ConfigInitDialog |
| POST | `/api/v1/query` | AI 对话（SSE） | conversation store |
| GET | `/api/v1/conversations` | 会话列表 | conversation-api |
| POST | `/api/v1/conversations` | 创建会话 | conversation-api |
| DELETE | `/api/v1/conversations/{id}` | 删除会话 | conversation-api |
| GET | `/api/v1/conversations/{id}/messages` | 获取消息 | conversation-api |
| PUT | `/api/v1/assistant/selection` | 同步选区 | assistant-api |
| GET | `/api/v1/assistant/selection/{id}` | 获取选区 | assistant-api |
| PUT | `/api/v1/assistant/written-context` | 同步文档 | assistant-api |
| GET | `/api/v1/assistant/written-context/{id}` | 获取文档 | assistant-api |
| GET | `/api/v1/library/items` | 论文列表 | library store |
| DELETE | `/api/v1/library/items/{id}` | 删除论文 | library store |
| POST | `/api/v1/library/items/{id}/retry` | 重试导入 | library store |
| POST | `/api/v1/import/start` | 开始导入 | library store |
| GET | `/api/v1/import/status/{id}` | 导入状态 | library store |
| GET | `/api/v1/papers/{id}/open` | PDF 代理 | library-api |

---

## 十二、设计系统

`style.css` 定义了完整的 CSS Variables 设计系统：

| 类别 | 变量示例 |
|------|----------|
| 颜色 | `--color-bg`、`--color-surface`、`--color-text`、`--color-primary` 等 30+ 变量 |
| 暗色主题 | `[data-theme="dark"]` 选择器覆盖所有颜色变量 |
| 间距 | `--space-xs` 到 `--space-2xl` |
| 圆角 | `--radius-sm/md/lg` |
| 字体 | `--font-sans`（系统无衬线）、`--font-mono`（等宽） |
| 阴影 | `--shadow-sm/md/lg` |
| 过渡 | `--transition-fast/normal` |
| 响应式 | 420px 断点适配 WPS 窄屏 |

---

## 十三、构建与开发

### 常用命令

```bash
cd frontend

# 安装依赖
pnpm install

# 开发模式（端口 3893，Vite 代理 /api → localhost:8000）
pnpm dev

# 构建（vue-tsc 类型检查 + vite build）
pnpm build

# 预览构建产物
pnpm preview

# 单元测试
pnpm test:unit

# E2E 测试
pnpm test:e2e
```

### 构建产物

```
dist/
├── app.html                  # 浏览器 SPA 入口
├── assets/                   # 编译后的 JS/CSS
├── cmaps/                    # CJK 字符映射
├── wps-plugin/
│   ├── taskpane.html         # WPS 任务窗格（IIFE 内联）
│   ├── main.html             # WPS 宿主桥
│   ├── main.js               # WPS 桥接 JS
│   └── ribbon.xml            # WPS 功能区定义
├── package.json              # WPS 插件标识
└── manifest.xml              # WPS 插件清单
```
