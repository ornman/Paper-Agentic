# 前端 WPS 集成改造计划

> 基于 Coronaaaaa 的 TODO.md，2026-05-29
> 目标：打通 WPS → 前端 → 后端的完整数据采集链路

---

## 零、现状诊断

### 已有能力（`wps.ts`）

| 能力 | 状态 | 问题 |
|------|------|------|
| `useWPSDetection()` | ✅ | 检测 `window.wps`，返回 `WPSApplication` |
| `useWPSSelection()` | ✅ | 有 `getSelectedText()` + `getDocumentContent()` |
| `useWPSPolling()` | ✅ | 5s 定时轮询选区 + 全文，自动调 `assistant-api` |
| `assistant-api.ts` | ✅ | `updateSelection()` / `updateWrittenContext()` 已对接后端 |

### 核心缺陷（对应 TODO）

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | 选区位置信息是假的（`start=0, end=text.length`） | 🔴 P0 | 引用定位完全不可用 |
| 2 | `SelectionChange` 直接赋值，多窗口切换丢失绑定 | 🔴 P0 | 数据采集链路断掉 |
| 3 | 没有防抖/节流，选区拖动时大量 API 调用 | 🟡 P2 | 后端可能被打爆 |
| 4 | 每次全量推送，无增量 diff | 🟡 P3 | 网络浪费 |
| 5 | `OnAddinLoad` 无状态初始化 | 🟠 P4 | 崩溃恢复后状态不同步 |
| 6 | `OnOpenPane` 无关闭回调 | 🟠 P4 | 关面板后轮询还在跑 |
| 7 | 错误恢复只有 `alert()` | 🟠 P4 | 用户体验差 |
| 8 | 无 WPS mock 测试层 | 🟢 P5 | CI 不可测 |

---

## 一、Phase 1：修复数据采集链路（P0）

> 目标：选区位置正确 + 事件绑定可靠 + 已写内容可采集

### 1.1 修复选区位置信息

**文件**：`frontend/src/composables/wps.ts`

**现状**：`SelectionInfo.start/end` 固定返回 `0` / `text.length`

**改动**：

```typescript
// 新增类型：完整的选区信息（含真实文档偏移量）
interface SelectionInfo {
  text: string
  start: number   // 文档中的真实起始偏移
  end: number     // 文档中的真实结束偏移
  source: 'selection' | 'range'
}

// 修改 getSelectedText → getSelectionInfo
function getSelectionInfo(): SelectionInfo | null {
  if (!isWPSAvailable.value || !wpsAPI.value) return null

  const selection = wpsAPI.value.ActiveWindow?.Selection
  if (!selection) return null

  // 优先用 Range（有真实偏移量）
  const range = selection.Range
  if (range?.Text) {
    return {
      text: range.Text.trim(),
      start: selection.Start,   // ← 真实偏移，不是 0
      end: selection.End,       // ← 真实偏移，不是 text.length
      source: 'range',
    }
  }

  // fallback：用 Selection.Text
  const text = (selection.Text || '').trim()
  if (!text) return null
  return {
    text,
    start: selection.Start,
    end: selection.End,
    source: 'selection',
  }
}
```

**涉及的连锁改动**：
- `useWPSPolling()` 中调用处从 `getSelectedText()` 改为 `getSelectionInfo()`
- `assistant-api.ts` 的 `updateSelection()` 需扩展为发送 `{ session_id, selection, start, end }`
- 后端 `/assistant/selection` 的 schema（`EditorSelectionUpdate`）需确认是否接受 `start/end` 字段，如不接受则需同步改

### 1.2 修复事件绑定稳定性

**文件**：`frontend/src/composables/wps.ts`

**现状**：`ActiveWindow.SelectionChange = handler` 直接赋值，切换窗口丢失

**策略**：**事件驱动（加速路径）+ 轮询（兜底路径）双保险**

```
用户划词
  │
  ├─→ SelectionChange 事件触发（~100ms 延迟）
  │     └─ 成功 → 立即推送选区
  │     └─ 失败 → 静默降级，等下一次 poll
  │
  └─→ 轮询定时器（3s 间隔兜底）
        └─ 检测选区是否变化 → 推送
```

**改动**：

```typescript
// 新增：事件驱动的选区监听（带自动重绑定）
export function useWPSSelectionChange(
  onChanged: (info: SelectionInfo) => void,
  options?: { debounceMs?: number }
) {
  const { wpsAPI, isWPSAvailable } = useWPSDetection()
  const debounceMs = options?.debounceMs ?? 300
  let timer: ReturnType<typeof setTimeout> | null = null
  let rebound = false

  function bindHandler() {
    if (!isWPSAvailable.value || !wpsAPI.value) return
    const win = wpsAPI.value.ActiveWindow
    if (!win) return

    win.SelectionChange = () => {
      // 防抖：300ms 内多次触发只执行最后一次
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => {
        const info = getSelectionInfo()
        if (info) onChanged(info)
      }, debounceMs)
    }
    rebound = false
  }

  // 轮询检查绑定是否丢失（每 2s 检查一次）
  function startRebindWatch() {
    // 简单策略：每次 poll 前重新 bind 一次
    // 即使旧绑定还在，重复赋值也无害
    setInterval(() => {
      if (isWPSAvailable.value) {
        bindHandler()
      }
    }, 2000)
  }

  return { bindHandler, startRebindWatch }
}
```

### 1.3 完善已写内容采集

**文件**：`frontend/src/composables/wps.ts`

**现状**：`getDocumentContent()` 已存在，但只在轮询里用，且每次推全量

**改动**：
- 保持 `getDocumentContent()` 不变（它在 `useWPSPolling` 里已经工作了）
- 增加去重逻辑：只在内容真正变化时才推（当前已有 `lastDocContent` 比对，基本 OK）
- 后续 Phase 3 再做增量 diff

**注意**：`ActiveDocument.Content.Text` 在长文档（>100 页）可能非常大（数 MB），当前全量推送在本地是 OK 的（127.0.0.1），不需要过早优化。

---

## 二、Phase 2：防抖 + 节流保护（P2）

> 目标：选区拖动不发起无效 API 调用

### 2.1 选区同步防抖

**文件**：`frontend/src/composables/wps.ts`

**策略**：

```
选区变化（拖动中）
  │
  ├─ 每次变化 → 更新内存中的 SelectionInfo
  │
  └─ debounce 300ms 后
       └─ 检查最终值是否与上次推送不同
            └─ 不同 → 调 updateSelection()
            └─ 相同 → 跳过
```

**改动**：在 `useWPSPolling.doPoll()` 的选区同步部分，将 `POLLING_INTERVAL` 从 5000ms 改为 3000ms，并在 `SelectionChange` 事件路径上加 300ms debounce（已在 1.2 中实现）。

### 2.2 文档全文同步节流

**改动**：
- 文档全文的 `updateWrittenContext()` 从每次轮询改为 **throttle 10s**：
  - 轮询间隔保持 3s（选区需要较快响应）
  - 但文档全文只在内容变化 + 距上次推送超过 10s 时才发
- 或者更简单：轮询间隔 3s，但 `lastDocContent` 比较保证不重复推送

---

## 三、Phase 3：增量同步（P3）

> 目标：只推变更部分，减少网络开销

### 3.1 文档全文增量 diff

**文件**：新建 `frontend/src/composables/use-doc-diff.ts`

**策略**：

```
首次：推全文 → 后端存为 baseline
后续：
  │
  ├─ 文档未变化 → 不推
  ├─ 文档追加（末尾新增） → 只推新增部分 + offset
  └─ 文档大改（>30% 不同） → 重新推全文（重置 baseline）
```

**实现**：

```typescript
export function useDocDiff() {
  let baseline: string = ''

  function computeDiff(newContent: string): { type: 'full' | 'append' | 'skip', content: string, offset?: number } {
    if (newContent === baseline) return { type: 'skip', content: '' }
    if (!baseline) {
      baseline = newContent
      return { type: 'full', content: newContent }
    }
    if (newContent.startsWith(baseline)) {
      const appended = newContent.slice(baseline.length)
      const offset = baseline.length
      baseline = newContent
      return { type: 'append', content: appended, offset }
    }
    // 文档大改 → 全量重置
    const changeRatio = 1 - longestCommonSubstring(baseline, newContent).length / Math.max(baseline.length, 1)
    if (changeRatio > 0.3) {
      baseline = newContent
      return { type: 'full', content: newContent }
    }
    // 中度变化 → 仍然全量（简单策略）
    baseline = newContent
    return { type: 'full', content: newContent }
  }

  return { computeDiff }
}
```

**后端影响**：`/assistant/written-context` 需支持 `mode: 'full' | 'append'` + `offset` 字段。当前后端 schema 无此字段 → **先 skip Phase 3，等 Phase 1-2 完成后与 Coronaaaaa 对齐**。

---

## 四、Phase 4：插件生命周期（P4）

> 目标：健壮的 WPS 插件加载/卸载/恢复

### 4.1 OnAddinLoad 状态初始化

**文件**：`frontend/wps-plugin/main.js`

**改动**：

```javascript
var PLUGIN_STATE = {
  initialized: false,
  taskPaneOpen: false,
  boundWindows: [],
}

function OnAddinLoad() {
  sendLog('wps', 'info', 'OnAddinLoad — 插件加载');
  console.log('[WPS Plugin] 宿主桥接层已加载');

  // 状态初始化
  PLUGIN_STATE.initialized = true;
  PLUGIN_STATE.taskPaneOpen = false;
  PLUGIN_STATE.boundWindows = [];

  // 注册 WPS 宿主事件
  try {
    if (typeof Application !== 'undefined' && Application.Documents) {
      // 监听文档切换 → 通知 Vue 应用重新绑定 SelectionChange
      // 具体通信通过 taskpane.html 的 postMessage
    }
  } catch (e) {
    sendLog('wps', 'warn', 'OnAddinLoad 事件注册失败: ' + e.message);
  }

  return true;
}
```

### 4.2 TaskPane 关闭回调

**文件**：`frontend/wps-plugin/main.js`

**改动**：

```javascript
function OnOpenPane() {
  sendLog('wps', 'info', 'OnOpenPane 被调用');

  try {
    // ... 现有逻辑 ...

    var taskPane = Application.CreateTaskPane(taskpaneUrl);
    taskPane.Title = 'AIForScience';
    taskPane.Visible = true;
    taskPane.DockPosition = 2;
    taskPane.Width = 400;

    // 新增：监听 TaskPane 关闭事件
    if (typeof taskPane.OnClose === 'function' || taskPane.OnClose === undefined) {
      // WPS 的 TaskPane 对象可能支持 OnClose 属性赋值
      taskPane.OnClose = function() {
        sendLog('wps', 'info', 'TaskPane 被用户关闭');
        PLUGIN_STATE.taskPaneOpen = false;
        // 通知 Vue 应用停止轮询（通过 postMessage）
        // 实际通信机制由 taskpane.html 中的 iframe 实现
      };
    }

    PLUGIN_STATE.taskPaneOpen = true;
    sendLog('wps', 'info', 'TaskPane 已打开');
    return true;
  } catch (error) {
    sendLog('wps', 'error', 'OnOpenPane 失败: ' + error.message);
    // 不再用 alert()，改用日志 + 降级
    console.error('[WPS Plugin] 打开 TaskPane 失败:', error.message);
    return false;
  }
}
```

### 4.3 错误恢复

**文件**：`frontend/wps-plugin/main.js`

**改动**：
- `OnOpenPane`：失败时不再 `alert()`，改为：
  1. 记录日志
  2. 如果 `Application` 对象可用但 `CreateTaskPane` 失败 → 延迟 2s 重试一次
  3. 两次都失败 → 静默降级（用户可手动点击 Ribbon 重试）
- Vue 应用侧：检测 WPS API 不可用时，自动切换到浏览器独立模式（`isDemoMode()` 或纯浏览器模式）

---

## 五、Phase 5：测试覆盖（P5）

> 目标：WPS composable 的逻辑分支可测试

### 5.1 Mock 层

**新建**：`frontend/src/composables/__tests__/wps.mock.ts`

```typescript
// 模拟 WPS 宿主环境，用于单元测试
export function createMockWPSApplication(overrides?: Partial<WPSApplication>): WPSApplication {
  return {
    ActiveDocument: {
      Content: { Text: '模拟文档全文内容' },
    },
    ActiveWindow: {
      Selection: {
        Text: '模拟选区文本',
        Start: 42,
        End: 56,
        Range: { Text: '模拟选区文本' },
      },
      SelectionChange: null,
    },
    ...overrides,
  }
}
```

### 5.2 测试用例

**新建**：`frontend/src/composables/__tests__/wps.test.ts`

覆盖：
- `getSelectionInfo()` — 正常返回 / 无选区 / API 不可用
- `getDocumentContent()` — 正常返回 / 空文档 / API 不可用
- `useDocDiff` — 首次全量 / 追加 / 无变化 / 大改全量
- debounce 逻辑 — 快速连续调用只触发一次

---

## 六、实施顺序 & 依赖

```
Phase 1.1 (选区位置修复)
  │
  ├─→ 后端 schema 确认（EditorSelectionUpdate 是否接受 start/end）
  │     └─ 不需改 → 直接做
  │     └─ 需改 → 等 Coronaaaaa 加字段
  │
  └─→ Phase 1.2 (事件绑定修复) ← 独立，可与 1.1 并行
        │
        └─→ Phase 1.3 (已写内容) ← 当前基本可用，微调即可

Phase 2 (防抖/节流) ← 依赖 1.2 的事件路径
  │
  └─→ Phase 3 (增量同步) ← 需要后端配合，先 skip

Phase 4 (插件生命周期) ← 独立，纯前端 main.js
Phase 5 (测试) ← 独立，可与 Phase 1 并行
```

### 建议执行批次

| 批次 | 内容 | 预计工作量 |
|------|------|-----------|
| **第一批** | Phase 1.1 + 1.2 + 1.3 | 2-3 小时 |
| **第二批** | Phase 2（防抖/节流） | 30 分钟 |
| **第三批** | Phase 4（插件生命周期） | 1 小时 |
| **第四批** | Phase 5（Mock 测试） | 1.5 小时 |
| **待定** | Phase 3（增量同步） | 需后端配合 |

---

## 七、涉及文件清单

| 文件 | 改动类型 | 所属 Phase |
|------|----------|------------|
| `frontend/src/composables/wps.ts` | 重构：选区信息结构、事件绑定、防抖 | 1.1, 1.2, 2 |
| `frontend/wps-plugin/main.js` | 修改：生命周期、错误恢复、关闭回调 | 4 |
| `frontend/src/services/assistant-api.ts` | 修改：`updateSelection` 增加 start/end | 1.1 |
| `frontend/src/composables/use-doc-diff.ts` | **新建**：增量 diff | 3（待定） |
| `frontend/src/composables/__tests__/wps.mock.ts` | **新建**：WPS mock 层 | 5 |
| `frontend/src/composables/__tests__/wps.test.ts` | **新建**：单元测试 | 5 |
| `backend/app/service_layer/schemas/assistant.py` | 确认：`EditorSelectionUpdate` 是否需扩展 | 1.1 |
