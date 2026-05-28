# 前端 Demo 样式优化 PRD

> 生成时间: 2026-05-28
> 范围: **仅前端 demo 样式调整**，不涉及后端改动
> 来源: 全面代码审计 + 用户反馈
> 状态: **~95% 完成**（2026-05-29 验证）

---

## 一、用户反馈修复（最高优先级）

### 1.1 顶栏 SVG 统一

**现象**: 汉堡菜单内联 SVG（20x20），新对话 `.icon-svg`（20x20），设置齿轮内联 SVG（18x18），大小不统一

**方案**:
- 设置齿轮改用 Fluent 风格 imported SVG（与 chat-add 风格一致）
- 所有 icon-button 内图标统一 20x20

**涉及**: `TopNavBar.vue`，新增 `src/assets/icons/settings.svg`

---

### 1.2 对话框展开图标替换 + 位置调整

**现状**: expand 按钮用 `expand.svg`（双箭头），位于输入区底部 `.input-actions` 内

**方案**:
- 替换为 `ci--expand.svg`（对角线展开角标，`stroke="currentColor"`）
- 位置从底部按钮组移到 **输入区右上角**
- expanded 状态下变为收起图标（旋转 180° 或换图标）

**涉及**: `InputBar.vue`，替换 `src/assets/icons/expand.svg`

### 1.3 发送按钮替换

**现状**: `send.svg` 用内嵌 gradient（#3bd5ff → #0094f0 → #ff6ce8），复杂且无法通过 `currentColor` 适配主题

**方案**:
- 替换为 `lets-icons--send.svg`（实心纸飞机，`fill="currentColor"`）
- `.send-btn` 保留渐变背景 `linear-gradient(135deg, #3bd5ff, #0094f0)`，图标通过 `color: #fff` 显示
- 风格与项目其他 Fluent 图标统一

**涉及**: `InputBar.vue`，替换 `src/assets/icons/send.svg`

---

### 1.3 停止生成功能

**现象**: AI 流式输出时无法中途停止

**方案**:
- `InputBar.vue`: `isBusy` 时发送按钮切换为停止图标（实心方形 `■` 或 Fluent stop 图标）
- `stores/conversation.ts`:
  - 新增 `abortController` ref，SSE 流使用 `AbortSignal`
  - `reset()` 时自动 abort
  - demo 模式调用 `mockSendPrompt` 返回的 `cancel()`
- 点击停止 → abort 流 + 标记最后一条 assistant 消息为截断状态

**涉及**: `InputBar.vue`, `ChatView.vue`, `stores/conversation.ts`

---

### 1.4 Demo 数据更新 — 多 paper 引用

**现状**: session-1 的 3 个 source 全是 `paper_id: 'paper-1'`，去重后只剩 1 个引用号

**方案**:
- session-1: sources 分布在 paper-1 和 paper-2
- session-2: sources 分布在 paper-2 和 paper-4
- 确保每条 AI 回复有 2-3 个不同 paper 的引用，让行内 `[1][2][3]` 标记生效

**涉及**: `demo/index.ts`

---

### 1.5 新对话过渡动画

**现象**: 点"新建对话" → 消息列表瞬间消失，EmptyState 瞬间出现

**方案**:
```html
<Transition name="fade" mode="out-in">
  <MessageList v-if="store.messages.length > 0" ... />
  <EmptyState v-else ... />
</Transition>
```
- 使用 `mode="out-in"` 先淡出再淡入，避免布局跳动

**涉及**: `ChatView.vue`

---

## 二、功能补全

### 2.1 消息操作栏

**现状**: 所有消息无操作按钮，无法复制/删除/重新生成

**方案**: 参考 `瑶绣·智问` 气泡设计文档，为用户和 AI 消息添加操作栏

#### AI 消息操作栏

**位置**: AI 消息底部，`sources-section` 下方，`1px solid var(--color-border-subtle)` 分隔

**生成中**:
```
AI 回复内容（打字中...）
───────────────────────────
[复制] [重新生成] [停止]
```

**生成完成**:
```
AI 回复内容
───────────────────────────
[复制] [重新生成] [追问] [删除]
```

| 按钮 | 生成中 | 完成 | 功能 |
|------|:------:|:----:|------|
| 复制 | ✅ | ✅ | `navigator.clipboard.writeText()` 复制纯文本，按钮变 "已复制" 2s |
| 重新生成 | ✅ | ✅ | 删除旧 AI 回复，以原用户问题重新调用 AI |
| 停止 | ✅ | ❌ | 中止流式输出（与 1.4 停止生成合并） |
| 追问 | ❌ | ✅ | 将 AI 回复摘要填入输入框，引导继续提问 |
| 删除 | ❌ | ✅ | 删除整组问答对（用户消息 + AI 回复） |

**按钮样式**: 图标 + 文字，灰色，hover 变 accent 色，无背景，紧凑排列

#### 用户消息操作栏

**位置**: 用户消息下方，默认隐藏，hover 气泡时淡入（`opacity 0→1, 200ms`）

```
用户消息内容...
               [复制] [编辑] [删除]    ← hover 时显示
```

| 按钮 | 功能 |
|------|------|
| 复制 | 复制消息纯文本 |
| 编辑 | 将内容填入输入框，可修改后重新发送 |
| 删除 | 从对话流中删除该条消息 |

**涉及**: `AIMessage.vue`, `UserMessage.vue`, `stores/conversation.ts`

---

### 2.2 错误状态展示

**现状**: `store.status === 'error'` 时无 UI 反馈，`store.errorMessage` 从未渲染

**方案**:
- MessageList 底部添加错误提示条
- 红色背景 + 错误信息 + "重试"按钮
- 随新消息出现自动消失

**涉及**: `MessageList.vue`, `ChatView.vue`

---

### 2.3 历史对话搜索

**现状**: HistoryPanel 无搜索框，会话多时难以定位

**方案**:
- HistoryPanel 顶部添加搜索输入框（与 LibraryPanel 搜索框样式一致）
- 按会话标题前端过滤
- 搜索框始终可见

**涉及**: `HistoryPanel.vue`

---

### 2.4 删除确认弹窗

**现状**: HistoryPanel 删除按钮无确认，误触即永久删除

**方案**:
- 点击删除 → 弹出确认对话框（"确定删除 'xxx' 会话？"）
- 使用 `window.confirm()` 或自定义 modal

**涉及**: `HistoryPanel.vue`, `ChatView.vue`

---

### 2.5 代码块复制按钮

**现状**: AI 回复中的代码块无复制功能

**方案**:
- 代码块右上角添加复制按钮（在 `.code-lang` 旁边或替代）
- 点击 → `navigator.clipboard.writeText()` → 按钮变为 ✓ 已复制
- 2 秒后恢复原状

**涉及**: `AIMessage.vue`

---

### 2.6 文献库排序

**现状**: 论文按后端返回顺序显示，无法排序

**方案**:
- LibraryPanel 搜索框右侧添加排序下拉（小图标）
- 选项: 按导入时间 / 按标题 / 按页数
- 纯前端排序，`computed` 根据排序方式排列

**涉及**: `LibraryPanel.vue`

---

### 2.7 上传进度 UI

**现状**: store 有 `importing`/`importPercent`/`importStep` 状态，但无 UI 渲染

**方案**:
- LibraryPanel 底部添加导入进度条（文件名 + 百分比 + 进度条）
- demo 模式下可 mock 进度动画
- 导入完成后自动隐藏

**涉及**: `LibraryPanel.vue`

---

### 2.8 面板切换动画

**现状**: 侧栏 history/library tab 切换内容无过渡

**方案**:
- SidebarDrawer tab 内容区添加 `<Transition name="fade" mode="out-in">`
- 切换时淡出旧面板 → 淡入新面板

**涉及**: `SidebarDrawer.vue`

---

### 2.9 历史面板空状态

**现状**: 纯文字"暂无历史记录"，无图标

**方案**:
- 添加空状态图标（如 Fluent clock/chat 图标）
- 样式与 LibraryPanel 空状态一致

**涉及**: `HistoryPanel.vue`

---

## 三、Bug 修复

### HIGH

| # | Bug | 位置 | 修复 |
|---|-----|------|------|
| 1 | **XSS: source.id 未转义** | `AIMessage.vue` `data-source-id` | `escapeHtml(source.id)` |
| 2 | **Demo 模式删除仍调 API** | `ChatView.vue:317` | `if (demoActive) { 本地删除; return }` |
| 3 | **expanded 收起后高度不恢复** | `InputBar.vue:184` | collapse 时 `textarea.style.height = 'auto'` |
| 4 | **`--font-size-body` 未定义** | `UserMessage.vue:28` | 改用 `--font-size-base` |
| 5 | **主题闪烁 FOUC** | `use-theme.ts` | 初始 theme 解析移到 module 级同步执行 |

### MEDIUM

| # | Bug | 位置 | 修复 |
|---|-----|------|------|
| 6 | **CitationPreview 超出屏幕** | `CitationPreview.vue` | viewport 边界 clamping |
| 7 | **CitationPreview 无消失动画** | `CitationPreview.vue` | `<Transition>` 包裹 |
| 8 | **Sidebar 无 Escape 关闭** | `SidebarDrawer.vue` | `@keydown.escape="close"` |
| 9 | **theme listener 泄漏** | `use-theme.ts` | `onUnmounted` 中 removeEventListener |

---

## 四、死代码清理

| 文件 | 删除项 |
|------|--------|
| `stores/ui.ts` | `modelPanelOpen`, `toggleModelPanel`, `closeModelPanel`, `toggleSidebar` |
| `stores/library.ts` | `searchQuery`, `filteredPapers` (computed), `paperCount`, `isPaperSelected`, `importFiles` |
| `stores/conversation.ts` | `currentSources()`, `lastAssistantMessage()` |
| `services/conversation-api.ts` | `getSession()` |
| `composables/wps.ts` | `useWPSSelectionChange()`, `openExternalUrl()`, `selectionInfo` |
| `CitationPreview.vue` | `@keyframes fadeIn` |
| `InputBar.vue` | `.expanded-meta` CSS |
| `SourcePanel.vue` | 整个文件删除 |

---

## 五、A11y 改进

| # | 修复 | 位置 |
|---|------|------|
| 1 | 历史条目加 `tabindex="0"` + `@keydown.enter` | `HistoryPanel.vue` |
| 2 | Sidebar 加 `role="dialog"` + `aria-modal="true"` | `SidebarDrawer.vue` |
| 3 | Tab 面板加 `role="tabpanel"` | `SidebarDrawer.vue` |
| 4 | MessageList 加 `role="log"` + `aria-live="polite"` | `MessageList.vue` |
| 5 | Source badge 加 `aria-label` | `AIMessage.vue` |
| 6 | Textarea 加 `aria-label="输入消息"` | `InputBar.vue` |
| 7 | 搜索框加 `aria-label` | `LibraryPanel.vue`, `HistoryPanel.vue` |
| 8 | Action chip 加 `:focus-visible` 样式 | `InputBar.vue` |

---

## 六、执行顺序

### 第一批：用户反馈（8 项）
1. 替换 send.svg → lets-icons 实心纸飞机
2. 顶栏 SVG 大小统一 + 设置图标改 imported
3. 停止生成功能（发送/停止按钮切换）
4. Demo 数据更新（多 paper 引用）
5. 新对话过渡动画
6. XSS 修复
7. `--font-size-body` → `--font-size-base`
8. 主题闪烁修复

### 第二批：功能补全（9 项）
9. 消息操作栏（AI: 复制/重新生成/追问/删除，用户: 复制/编辑/删除）
10. 错误状态展示 UI
11. 历史对话搜索
12. 删除确认弹窗
13. 代码块复制按钮
14. 文献库排序
15. 上传进度 UI
16. 面板切换动画
17. 历史面板空状态

### 第三批：清理 + A11y（3 项）
18. 死代码清理
19. A11y 改进
20. Sidebar / CitationPreview 小 bug 修复

**总计 20 项**

---

## 七、范围说明

**本轮只做前端 demo 样式调整，以下功能不涉及后端改动：**
- 拖拽上传（前端事件绑定即可，demo 模式下不影响）
- 上传进度 UI（demo 模式可 mock 进度）
- 文件夹上传
- 后端 multipart 上传端点
- 后端批量删除端点

**这些后端依赖项留到下一轮后端同步迭代时处理。**
