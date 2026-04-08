# MVP Frontend WPS Sidebar Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有 Vue 原型重构为 WPS 文字场景下的右侧常驻论文创作 RAG 辅助侧边栏，打通知识库导入、文档轮询、灵感按钮场景 1 请求、流式回复与来源卡片展示闭环。

**Architecture:** 保留 `frontend/` 作为正式 Vue 3 + Pinia UI 工程，同时吸收 `D:/同步/.tools/wps-debug` 中已经验证成功的 WPS 插件桥接模式。第一版只支持 WPS 文字，只实现单会话消息流与知识库一级入口，不做完整历史会话与多场景交互。

**Tech Stack:** Vue 3, Pinia, TypeScript, Vite, WPSJS TaskPane / Ribbon, SSE, Playwright, 本地后端 API。

---

## Implementation Rules

- 执行时使用 `@superpowers:executing-plans`
- 每个任务严格先写测试，再写最小实现，再跑测试
- 每个完成块都运行验证命令，不要跳过
- WPSJS / 插件 API / 小众概念优先查 `D:/同步/.tools/rag`
- WPS 宿主桥接优先参考 `D:/同步/.tools/wps-debug`
- 第一版只支持 WPS 文字
- 第一版默认知识库导入模式固定为 `brute`
- 第一版主入口是“获取灵感”，不是通用聊天发送

---

### Task 1: 重构现有 Vue 原型为前端壳层骨架

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/style.css`
- Create: `frontend/src/app/AppShell.vue`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/types/host.ts`
- Create: `frontend/src/types/library.ts`
- Create: `frontend/src/types/conversation.ts`
- Test: `frontend/src/app/__tests__/app-shell.spec.ts`

**Step 1: Write the failing test**

```ts
it('renders top nav, knowledge bar, content area, and bottom action bar', () => {
  const wrapper = mount(AppShell)
  expect(wrapper.find('[data-testid="top-nav"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="knowledge-bar"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="content-area"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="bottom-action-bar"]').exists()).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test app-shell`
Expected: FAIL because `AppShell.vue` and test setup do not exist yet.

**Step 3: Write minimal implementation**

- 把现有 `App.vue` 从旧的 TabBar/TabContent 原型切换到新的 `AppShell.vue`
- 用 `tokens.css` 建立基础设计 token：
  - 白底
  - 浅灰分隔
  - 中性文字
  - 克制蓝色强调
- 定义最小类型：
  - `HostSnapshot`
  - `LibrarySummary`
  - `ConversationMessage`

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test app-shell`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/App.vue frontend/src/main.ts frontend/src/style.css frontend/src/app/AppShell.vue frontend/src/styles/tokens.css frontend/src/types/host.ts frontend/src/types/library.ts frontend/src/types/conversation.ts
git commit -m "refactor: replace tab prototype with sidebar shell"
```

---

### Task 2: 搭建右侧侧边栏布局组件

**Files:**
- Create: `frontend/src/components/layout/SidebarContainer.vue`
- Create: `frontend/src/components/layout/TopNavBar.vue`
- Create: `frontend/src/components/layout/KnowledgeBar.vue`
- Create: `frontend/src/components/layout/BottomActionBar.vue`
- Create: `frontend/src/components/conversation/EmptyState.vue`
- Create: `frontend/src/components/overlays/HistoryDrawer.vue`
- Test: `frontend/src/components/layout/__tests__/sidebar-layout.spec.ts`

**Step 1: Write the failing test**

```ts
it('renders a 380px right sidebar layout with nav, knowledge bar, empty state, and action bar', () => {
  const wrapper = mount(SidebarContainer)
  expect(wrapper.findComponent(TopNavBar).exists()).toBe(true)
  expect(wrapper.findComponent(KnowledgeBar).exists()).toBe(true)
  expect(wrapper.findComponent(EmptyState).exists()).toBe(true)
  expect(wrapper.findComponent(BottomActionBar).exists()).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test sidebar-layout`
Expected: FAIL because layout components do not exist yet.

**Step 3: Write minimal implementation**

- 顶部栏：历史按钮 / 标题 / 新建 / 收起
- 知识库状态层：文献数量、状态、导入入口
- 空态：创作导向引导文案 + “获取灵感”主按钮
- 底部栏：输入框壳 + 灵感按钮 + 功能按钮壳
- 保持“Copilot 办公专业版”克制风格，不使用花哨装饰
- `HistoryDrawer.vue` 先只做打开/关闭壳

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test sidebar-layout`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/layout frontend/src/components/conversation/EmptyState.vue frontend/src/components/overlays/HistoryDrawer.vue
git commit -m "feat: add sidebar layout skeleton"
```

---

### Task 3: 建立 Pinia 状态中心与基础 UI 状态流

**Files:**
- Create: `frontend/src/stores/host.ts`
- Create: `frontend/src/stores/library.ts`
- Create: `frontend/src/stores/conversation.ts`
- Create: `frontend/src/stores/ui.ts`
- Test: `frontend/src/stores/__tests__/state-machines.spec.ts`

**Step 1: Write the failing test**

```ts
it('transitions conversation state from idle to requesting to streaming to done', () => {
  const store = useConversationStore()
  store.startRequest()
  expect(store.status).toBe('requesting')
  store.startStreaming()
  expect(store.status).toBe('streaming')
  store.finishResponse()
  expect(store.status).toBe('done')
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test state-machines`
Expected: FAIL because stores do not exist yet.

**Step 3: Write minimal implementation**

- `host.ts`：booting / ready / no_document / polling / stale / error
- `library.ts`：unavailable / empty / ready / importing / error
- `conversation.ts`：idle / requesting / streaming / done / error
- `ui.ts`：historyDrawerOpen / sidebarExpanded / toastMessage
- 不接真实 API，只建立状态骨架和最小 mutation/action

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test state-machines`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/stores
git commit -m "feat: add frontend state stores"
```

---

### Task 4: 迁移 WPS 插件宿主桥接层

**Files:**
- Create: `frontend/wps-plugin/main.js`
- Create: `frontend/wps-plugin/ribbon.xml`
- Create: `frontend/wps-plugin/taskpane.html`
- Create: `frontend/src/services/wps-host.ts`
- Modify: `frontend/vite.config.ts`
- Test: `frontend/src/services/__tests__/wps-host.spec.ts`

**Step 1: Write the failing test**

```ts
it('exposes a host adapter that can start polling and report document availability', async () => {
  const host = createWpsHostAdapter(fakeWpsApi())
  await host.startPolling()
  expect(host.getSnapshot().available).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test wps-host`
Expected: FAIL because host adapter and plugin shell do not exist yet.

**Step 3: Write minimal implementation**

- 从 `D:/同步/.tools/wps-debug/test-plugin/main.js` 吸收：
  - `GetUrlPath()`
  - `Application.CreateTaskPane()`
  - `DockPosition = 2`
  - Ribbon 回调结构
- 在正式工程建立 `wps-plugin/`：
  - `main.js`
  - `ribbon.xml`
  - `taskpane.html`
- 在 `wps-host.ts` 中封装最小宿主桥接
- `vite.config.ts` 兼容 TaskPane 静态入口

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test wps-host`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/wps-plugin frontend/src/services/wps-host.ts frontend/vite.config.ts
git commit -m "feat: add WPS plugin host bridge"
```

---

### Task 5: 接入 WPS 轮询并驱动空态 / 可用态切换

**Files:**
- Modify: `frontend/src/services/wps-host.ts`
- Modify: `frontend/src/stores/host.ts`
- Modify: `frontend/src/app/AppShell.vue`
- Modify: `frontend/src/components/conversation/EmptyState.vue`
- Test: `frontend/src/services/__tests__/wps-polling.spec.ts`

**Step 1: Write the failing test**

```ts
it('updates host store every 5 seconds with current document text snapshot', async () => {
  const store = useHostStore()
  const host = createWpsHostAdapter(fakePollingWpsApi('论文正文内容'))
  await host.pollOnce(store)
  expect(store.text).toContain('论文正文内容')
  expect(store.available).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test wps-polling`
Expected: FAIL because polling logic is not wired.

**Step 3: Write minimal implementation**

- 轮询周期固定 5 秒
- 写入 `hostStore`：
  - `docTitle`
  - `text`
  - `updatedAt`
  - `available`
- 空态根据 `hostStore.available` 调整引导文案
- 不把轮询内容推给后端，只缓存于前端

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test wps-polling`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/services/wps-host.ts frontend/src/stores/host.ts frontend/src/app/AppShell.vue frontend/src/components/conversation/EmptyState.vue
git commit -m "feat: wire WPS polling into host state"
```

---

### Task 6: 接入知识库状态与 PDF 路径导入

**Files:**
- Create: `frontend/src/services/api-client.ts`
- Modify: `frontend/src/stores/library.ts`
- Modify: `frontend/src/components/layout/KnowledgeBar.vue`
- Modify: `frontend/src/components/library/ImportPdfButton.vue`
- Test: `frontend/src/services/__tests__/library-api.spec.ts`
- Test: `frontend/src/components/library/__tests__/import-path-validation.spec.ts`

**Step 1: Write the failing test**

```ts
it('rejects invalid local PDF paths before calling the backend', async () => {
  const result = validatePdfPathInput('https://evil.test/a.pdf')
  expect(result.ok).toBe(false)
  expect(result.message).toContain('输入有误')
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test library-api`
Expected: FAIL because api client and path validation do not exist.

**Step 3: Write minimal implementation**

- `GET /api/v1/library/documents`
- `POST /api/v1/library/import`
- 第一版默认 `index_mode = brute`
- 前端前置校验：
  - 为空
  - 不是本地路径
  - 不是 `.pdf`
  -> 直接提示“输入有误”
- 导入中 / 成功 / 失败状态回写 `libraryStore`

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test library-api`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/services/api-client.ts frontend/src/stores/library.ts frontend/src/components/layout/KnowledgeBar.vue frontend/src/components/library/ImportPdfButton.vue
git commit -m "feat: add library status and PDF import"
```

---

### Task 7: 搭单会话消息流与来源卡片组件

**Files:**
- Create: `frontend/src/components/conversation/MessageList.vue`
- Create: `frontend/src/components/conversation/UserActionMessage.vue`
- Create: `frontend/src/components/conversation/AssistantMessage.vue`
- Create: `frontend/src/components/conversation/SourceCardList.vue`
- Modify: `frontend/src/stores/conversation.ts`
- Test: `frontend/src/components/conversation/__tests__/message-flow.spec.ts`

**Step 1: Write the failing test**

```ts
it('renders an assistant answer with attached source cards', () => {
  const wrapper = mount(AssistantMessage, {
    props: {
      message: {
        role: 'assistant',
        content: '建议从公共文化服务数字化角度切入。',
        sources: [{ title: '文献A', page: 12, snippet: '...' }]
      }
    }
  })
  expect(wrapper.text()).toContain('参考来源')
  expect(wrapper.text()).toContain('文献A')
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test message-flow`
Expected: FAIL because conversation components do not exist.

**Step 3: Write minimal implementation**

- 单会话消息列表
- 用户动作消息（不是普通聊天输入）
- 助手回复消息
- 来源卡片列表
- 来源区是回复的一部分，不是附件列表

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test message-flow`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/conversation frontend/src/stores/conversation.ts
git commit -m "feat: add single-session message flow UI"
```

---

### Task 8: 接入场景 1 灵感按钮闭环与 SSE 流式回复

**Files:**
- Create: `frontend/src/services/sse-client.ts`
- Modify: `frontend/src/components/layout/BottomActionBar.vue`
- Modify: `frontend/src/stores/conversation.ts`
- Modify: `frontend/src/app/AppShell.vue`
- Test: `frontend/src/services/__tests__/ask-inspiration.spec.ts`

**Step 1: Write the failing test**

```ts
it('sends scene-1 request with current host text and streams answer chunks plus sources', async () => {
  const store = useConversationStore()
  const hostStore = useHostStore()
  hostStore.text = '当前论文正文内容'

  await askInspiration(hostStore, store, fakeSseServer())

  expect(store.messages.at(-1)?.role).toBe('assistant')
  expect(store.messages.at(-1)?.content).toContain('灵感建议')
  expect(store.messages.at(-1)?.sources?.length).toBeGreaterThan(0)
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test ask-inspiration`
Expected: FAIL because SSE client and inspiration action do not exist.

**Step 3: Write minimal implementation**

- `BottomActionBar.vue` 主按钮固定为“获取灵感”
- 调 `POST /api/v1/query/ask`
- 请求体固定场景 1：
  - `text = hostStore.text`
  - `user_text = ''`
  - `user_prompt = ''`
  - `index_mode = 'brute'`
- 处理 SSE：
  - `chunk`
  - `sources`
  - `done`
  - `error`
- 消息区显示用户动作消息 + 助手回复 + 来源卡片

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test ask-inspiration`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/services/sse-client.ts frontend/src/components/layout/BottomActionBar.vue frontend/src/stores/conversation.ts frontend/src/app/AppShell.vue
git commit -m "feat: wire inspiration button to scene-1 SSE flow"
```

---

### Task 9: 补历史抽屉壳与新建对话重置逻辑

**Files:**
- Modify: `frontend/src/components/overlays/HistoryDrawer.vue`
- Modify: `frontend/src/components/layout/TopNavBar.vue`
- Modify: `frontend/src/stores/ui.ts`
- Modify: `frontend/src/stores/conversation.ts`
- Test: `frontend/src/components/overlays/__tests__/history-drawer-shell.spec.ts`

**Step 1: Write the failing test**

```ts
it('opens history drawer shell and resets to empty state on new conversation', async () => {
  const ui = useUiStore()
  const conversation = useConversationStore()
  ui.openHistoryDrawer()
  expect(ui.historyDrawerOpen).toBe(true)
  conversation.resetConversation()
  expect(conversation.messages).toEqual([])
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test history-drawer-shell`
Expected: FAIL because drawer shell and reset action are incomplete.

**Step 3: Write minimal implementation**

- 历史抽屉开/关壳
- 顶部历史按钮与新建按钮接入 store
- 新建对话后清空当前单会话消息流
- 不接真实历史会话数据

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test history-drawer-shell`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/overlays/HistoryDrawer.vue frontend/src/components/layout/TopNavBar.vue frontend/src/stores/ui.ts frontend/src/stores/conversation.ts
git commit -m "feat: add history drawer shell and new conversation reset"
```

---

### Task 10: 跑前端闭环验证并对接 WPS 宿主测试路径

**Files:**
- Modify: `frontend/wps-plugin/main.js`
- Modify: `frontend/wps-plugin/ribbon.xml`
- Create: `frontend/tests/e2e/wps-sidebar-smoke.md`
- Create: `frontend/tests/e2e/frontend-acceptance-checklist.md`

**Step 1: Write the failing test / checklist**

```md
- [ ] 打开插件后显示右侧侧边栏
- [ ] 轮询到当前文档内容
- [ ] 错误 PDF 路径提示“输入有误”
- [ ] 正确路径导入成功并更新知识库状态
- [ ] 点击“获取灵感”后收到流式回复
- [ ] 回复包含来源卡片
```

**Step 2: Run verification to observe current failures**

Run: `cd frontend && pnpm build`
Expected: If integration incomplete, build or manual flow reveals remaining gaps.

**Step 3: Write minimal implementation**

- 把正式 Vue 产物接到 WPS TaskPane 壳上
- 校正 Ribbon 按钮打开正式侧边栏入口
- 保证开发产物与 WPS 宿主路径兼容
- 输出前端验收清单与 WPS 烟雾测试手册

**Step 4: Run verification to confirm it works**

Run: `cd frontend && pnpm build`
Expected: PASS.

Then run a manual / Playwright-assisted smoke test against WPS host.

**Step 5: Commit**

```bash
git add frontend/wps-plugin frontend/tests/e2e
git commit -m "feat: finalize WPS sidebar frontend integration"
```

---

## Final Verification Checklist

- [ ] 正式侧边栏骨架已替换旧 Tab 原型
- [ ] WPS TaskPane 宿主桥接已迁移进正式前端工程
- [ ] 每 5 秒轮询当前 WPS 文字文档内容
- [ ] 知识库状态条为一级入口
- [ ] PDF 路径输入错误时立即提示“输入有误”
- [ ] `GET /library/documents` 已驱动知识库状态
- [ ] `POST /library/import` 已打通导入
- [ ] “获取灵感”按钮已走场景 1 SSE 闭环
- [ ] 回复必须显示来源卡片
- [ ] 默认风格为克制的办公专业版，不花哨
- [ ] 第一版只支持 WPS 文字

Plan complete and saved to `docs/plans/2026-03-25-mvp-frontend-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - 我逐任务执行、每步校验、每块做代码复审

**2. Parallel Session (separate)** - 新会话用 `superpowers:executing-plans` 按计划批量推进

**Which approach?**
