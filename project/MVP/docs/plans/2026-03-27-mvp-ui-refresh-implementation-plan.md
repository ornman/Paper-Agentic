# MVP UI Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把当前已跑通的正式版前端重构为更像成熟办公产品的高质量 UI，显著提升整体高级感、可信度与展示说服力，同时不破坏现有 WPS 宿主、知识库导入、轮询、消息流与灵感按钮闭环。

**Architecture:** 保持现有 Vue 3 + Pinia + WPS 宿主桥接 + SSE 功能链路不变，只重构视觉语言、版式层级和高频组件表现。先统一 design tokens 和全局样式，再重构壳层骨架、知识库状态条、输入区、消息卡片与来源卡片，最后做浏览器级截图与 WPSJS debug 验证。

**Tech Stack:** Vue 3, Pinia, TypeScript, Vite, scoped CSS, Vitest, Playwright, WPSJS TaskPane。

---

## Implementation Rules

- 执行时使用 `@superpowers:executing-plans`
- 每个任务严格先写测试，再写最小实现，再跑测试
- 每个任务完成后至少跑对应定向测试；阶段结束后跑 `pnpm test` 与 `pnpm build`
- 这轮是 **UI/UX Pro Max 重构**，不是功能扩展；除非为保持现有链路可用所必须，不改前后端功能语义
- 保持“论文创作 RAG 辅助插件”定位，不往通用聊天助手方向漂移
- 知识库状态层是一级视觉入口；来源区必须仍然是回复的一部分
- 不提交 git

---

### Task 1: 重构 design tokens 与全局视觉基线

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/style.css`
- Test: `frontend/src/app/__tests__/app-shell.spec.ts`

**Step 1: Write the failing test**

```ts
it('exposes the refreshed visual tokens needed by the shell', () => {
  const styles = getComputedStyle(document.documentElement)
  expect(styles.getPropertyValue('--color-surface-base').trim()).toBeTruthy()
  expect(styles.getPropertyValue('--color-accent').trim()).toBeTruthy()
  expect(styles.getPropertyValue('--space-4').trim()).toBeTruthy()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- src/app/__tests__/app-shell.spec.ts`
Expected: FAIL because the new token expectations are not defined yet.

**Step 3: Write minimal implementation**

```css
:root {
  --color-surface-base: #ffffff;
  --color-surface-muted: #f6f7f9;
  --color-border-subtle: #e6e8ee;
  --color-text-primary: #111827;
  --color-text-secondary: #6b7280;
  --color-accent: #2563eb;
  --radius-md: 14px;
  --space-4: 16px;
}
```

- 统一背景层、文本层、强调层、边框、圆角、间距 token
- 调整全局 reset、滚动条、焦点态，让页面第一眼更像成熟办公产品

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test -- src/app/__tests__/app-shell.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/style.css frontend/src/app/__tests__/app-shell.spec.ts
git commit -m "feat: refresh global design tokens and visual baseline"
```

---

### Task 2: 重构顶层壳与导航、知识库层级

**Files:**
- Modify: `frontend/src/app/AppShell.vue`
- Modify: `frontend/src/components/layout/TopNavBar.vue`
- Modify: `frontend/src/components/layout/KnowledgeBar.vue`
- Modify: `frontend/src/components/layout/SidebarContainer.vue`
- Test: `frontend/src/components/layout/__tests__/sidebar-layout.spec.ts`

**Step 1: Write the failing test**

```ts
it('renders a stronger product hierarchy with nav, knowledge bar, content area, and action bar', () => {
  const wrapper = mount(SidebarContainer, { global: { plugins: [createPinia()] } })
  expect(wrapper.find('[data-testid="top-nav"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="knowledge-bar"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="content-area"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="bottom-action-bar"]').exists()).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- src/components/layout/__tests__/sidebar-layout.spec.ts`
Expected: FAIL because the refreshed hierarchy is not implemented yet.

**Step 3: Write minimal implementation**

```vue
<header class="top-nav">...</header>
<section class="knowledge-bar">...</section>
<main class="sidebar-main">...</main>
<footer class="bottom-action-bar">...</footer>
```

- `TopNavBar` 做成更像产品导航，而不是按钮排排坐
- `KnowledgeBar` 做成“价值证明条”，弱化后台信息卡感
- `AppShell/SidebarContainer` 统一整体节奏、留白和层级关系

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test -- src/components/layout/__tests__/sidebar-layout.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/app/AppShell.vue frontend/src/components/layout/TopNavBar.vue frontend/src/components/layout/KnowledgeBar.vue frontend/src/components/layout/SidebarContainer.vue frontend/src/components/layout/__tests__/sidebar-layout.spec.ts
git commit -m "feat: rebuild shell hierarchy and knowledge bar"
```

---

### Task 3: 新增 ContextHintBar 并重构 BottomActionBar

**Files:**
- Create: `frontend/src/components/layout/ContextHintBar.vue`
- Modify: `frontend/src/components/layout/BottomActionBar.vue`
- Modify: `frontend/src/app/AppShell.vue`
- Test: `frontend/src/services/__tests__/wps-polling.spec.ts`
- Test: `frontend/src/services/__tests__/ask-inspiration.spec.ts`

**Step 1: Write the failing test**

```ts
it('shows context hint above the composer and keeps send as the primary action', async () => {
  const wrapper = mount(AppShell, { global: { plugins: [createPinia()] } })
  expect(wrapper.find('[data-testid="context-hint-bar"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="send-button"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="inspire-button"]').exists()).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- src/services/__tests__/wps-polling.spec.ts src/services/__tests__/ask-inspiration.spec.ts`
Expected: FAIL because ContextHintBar and the new action hierarchy do not exist yet.

**Step 3: Write minimal implementation**

```vue
<ContextHintBar
  :host-status="hostStore.status"
  :selection-status="hostStore.selectionStatus"
  :selection-preview="hostStore.selectionPreview"
/>
<textarea placeholder="描述你想推进的论证、段落或写作目标..." />
<button data-testid="send-button">发送</button>
<button data-testid="inspire-button">获取灵感</button>
```

- `BottomActionBar` 从“按钮区”升级成“工作输入台”
- `发送` 变成正式主入口
- `获取灵感` 降为次入口但继续保留
- `ContextHintBar` 展示“当前文档/当前选区/降级语义”
- 现有“补充需求”输入框从灰 disabled demo 感改成正式输入台

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test -- src/services/__tests__/wps-polling.spec.ts src/services/__tests__/ask-inspiration.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/layout/ContextHintBar.vue frontend/src/components/layout/BottomActionBar.vue frontend/src/app/AppShell.vue frontend/src/services/__tests__/wps-polling.spec.ts frontend/src/services/__tests__/ask-inspiration.spec.ts
git commit -m "feat: add context hint bar and rebuild action area"
```

---

### Task 4: 重构空态为“待工作状态”而不是占位图

**Files:**
- Modify: `frontend/src/components/conversation/EmptyState.vue`
- Test: `frontend/src/services/__tests__/wps-polling.spec.ts`

**Step 1: Write the failing test**

```ts
it('renders a work-ready empty state rather than a generic chat placeholder', () => {
  const wrapper = mount(EmptyState, { global: { plugins: [createPinia()] } })
  expect(wrapper.text()).toContain('论文创作辅助')
  expect(wrapper.text()).toContain('获取灵感')
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- src/services/__tests__/wps-polling.spec.ts`
Expected: FAIL because empty-state copy and hierarchy do not match the new design.

**Step 3: Write minimal implementation**

```vue
<p class="eyebrow">论文创作辅助</p>
<h1>围绕当前草稿与知识库推进写作</h1>
<p>不是聊天入口，而是创作任务入口。</p>
```

- 强化“系统已准备好工作”的感受
- 保留空态的克制感，不做大 logo 和花哨插画
- `stale / ready / no_document` 三类文案继续存在，但更像成熟产品

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test -- src/services/__tests__/wps-polling.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/conversation/EmptyState.vue frontend/src/services/__tests__/wps-polling.spec.ts
git commit -m "feat: redesign empty state as work-ready panel"
```

---

### Task 5: 重构消息列表与用户动作消息的工作流感

**Files:**
- Modify: `frontend/src/components/conversation/MessageList.vue`
- Modify: `frontend/src/components/conversation/UserActionMessage.vue`
- Test: `frontend/src/components/conversation/__tests__/message-flow.spec.ts`

**Step 1: Write the failing test**

```ts
it('renders user messages as explicit writing actions rather than generic chat bubbles', () => {
  const wrapper = mount(UserActionMessage, {
    props: { message: { id: '1', role: 'user', kind: 'action', content: '帮我补这一段的理论支撑', createdAt: '2026-03-27T00:00:00Z' } }
  })
  expect(wrapper.text()).toContain('触发动作')
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- src/components/conversation/__tests__/message-flow.spec.ts`
Expected: FAIL because the visual treatment has not been updated.

**Step 3: Write minimal implementation**

```vue
<article class="user-action-message">
  <p class="label">触发动作</p>
  <p class="content">{{ message.content }}</p>
</article>
```

- 弱化普通聊天感
- 把用户消息做成“任务卡”
- 保持单会话消息顺序不变

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test -- src/components/conversation/__tests__/message-flow.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/conversation/MessageList.vue frontend/src/components/conversation/UserActionMessage.vue frontend/src/components/conversation/__tests__/message-flow.spec.ts
git commit -m "feat: restyle user action flow in message list"
```

---

### Task 6: 重构助手回复与来源卡片为“建议正文 + 证据层”

**Files:**
- Modify: `frontend/src/components/conversation/AssistantMessage.vue`
- Modify: `frontend/src/components/conversation/SourceCardList.vue`
- Test: `frontend/src/components/conversation/__tests__/message-flow.spec.ts`

**Step 1: Write the failing test**

```ts
it('renders assistant advice with an embedded evidence layer', () => {
  const wrapper = mount(AssistantMessage, {
    props: {
      message: {
        id: 'a1',
        role: 'assistant',
        kind: 'answer',
        content: '建议先补理论框架，再引案例。',
        createdAt: '2026-03-27T00:00:00Z',
        sources: [{ id: 's1', title: '文献A', page: 7, snippet: '...' }]
      }
    }
  })
  expect(wrapper.text()).toContain('参考来源')
  expect(wrapper.text()).toContain('文献A')
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- src/components/conversation/__tests__/message-flow.spec.ts`
Expected: FAIL because the layered visual treatment is not implemented yet.

**Step 3: Write minimal implementation**

```vue
<div class="assistant-body">...</div>
<div class="assistant-evidence">
  <SourceCardList :sources="message.sources" />
</div>
```

- 助手回复分为“正文区 + 来源证据层”
- 来源卡片更像证据，不像附件列表
- 提升可信度与产品说服力

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test -- src/components/conversation/__tests__/message-flow.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/conversation/AssistantMessage.vue frontend/src/components/conversation/SourceCardList.vue frontend/src/components/conversation/__tests__/message-flow.spec.ts
git commit -m "feat: redesign assistant reply and evidence cards"
```

---

### Task 7: 重构知识库状态条为一级价值入口

**Files:**
- Modify: `frontend/src/components/layout/KnowledgeBar.vue`
- Modify: `frontend/src/components/library/ImportPdfButton.vue`
- Modify: `frontend/src/stores/library.ts`
- Test: `frontend/src/services/__tests__/library-api.spec.ts`
- Test: `frontend/src/components/library/__tests__/import-path-validation.spec.ts`

**Step 1: Write the failing test**

```ts
it('renders the library bar as a primary product state strip rather than a utility row', async () => {
  const wrapper = mount(KnowledgeBar, { global: { plugins: [createPinia()] } })
  expect(wrapper.text()).toContain('知识库')
  expect(wrapper.find('[data-testid="import-pdf-button"]').exists()).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- src/services/__tests__/library-api.spec.ts src/components/library/__tests__/import-path-validation.spec.ts`
Expected: FAIL because the visual hierarchy has not been refreshed yet.

**Step 3: Write minimal implementation**

```vue
<section class="knowledge-bar">
  <div class="summary">...</div>
  <div class="status">...</div>
  <ImportPdfButton />
</section>
```

- 提升知识库层的产品感和识别度
- 保留“输入有误 / 读取失败 / 导入失败”语义
- 不引入完整知识库管理页

**Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test -- src/services/__tests__/library-api.spec.ts src/components/library/__tests__/import-path-validation.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/layout/KnowledgeBar.vue frontend/src/components/library/ImportPdfButton.vue frontend/src/stores/library.ts frontend/src/services/__tests__/library-api.spec.ts frontend/src/components/library/__tests__/import-path-validation.spec.ts
git commit -m "feat: redesign knowledge bar as core product strip"
```

---

### Task 8: 微交互、错误态与 WPSJS 验证截图收尾

**Files:**
- Modify: `frontend/src/app/AppShell.vue`
- Modify: `frontend/src/components/layout/HistoryDrawer.vue`
- Modify: `frontend/tests/e2e/wpsjs_debug_http_probe.py`
- Modify: `frontend/tests/e2e/wpsjs_debug_browser_validation.py`
- Test: `frontend/src/services/__tests__/wps-polling.spec.ts`

**Step 1: Write the failing test / checklist**

```md
- [ ] 顶部栏、知识库条、内容区、输入区视觉层级统一
- [ ] 错误提示是克制的块级提示，不是醒目警报
- [ ] 历史抽屉壳与主界面视觉统一
- [ ] 浏览器级 WPSJS debug 验证截图已更新
```

**Step 2: Run verification to observe current gaps**

Run: `cd frontend && pnpm test && pnpm build`
Expected: Identify remaining rough edges in states/visual consistency.

**Step 3: Write minimal implementation**

- 统一错误块、loading、按钮 hover、空态/消息态的过渡感
- 历史抽屉壳风格跟随新系统
- 更新 Playwright 截图脚本，重新生成验证图

**Step 4: Run verification to confirm it passes**

Run: `cd frontend && pnpm test && pnpm build`
Expected: PASS.

Then run the existing WPSJS browser-level validation scripts and inspect screenshots.

**Step 5: Commit**

```bash
git add frontend/src/app/AppShell.vue frontend/src/components/layout/HistoryDrawer.vue frontend/tests/e2e
git commit -m "feat: polish ui states and refresh WPSJS validation artifacts"
```

---

## Final Verification Checklist

- [ ] 视觉 token 已统一为更高级、更克制的产品语言
- [ ] 顶部栏更像产品导航，而不是按钮条
- [ ] 知识库状态层是一眼可见的一级入口
- [ ] 输入区成为正式工作输入台
- [ ] 发送为主入口，获取灵感为次入口
- [ ] 空态、工作态、错误态、加载态视觉差异清楚
- [ ] 助手回复呈现“建议正文 + 来源证据层”
- [ ] 来源卡片更像证据，不像附件
- [ ] 全量前端测试通过
- [ ] 前端构建通过
- [ ] WPSJS debug 浏览器级截图已更新

Plan complete and saved to `docs/plans/2026-03-27-mvp-ui-refresh-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - 我逐任务执行、每步校验、每块做代码复审

**2. Parallel Session (separate)** - 新会话用 `superpowers:executing-plans` 按计划批量推进

**Which approach?**
