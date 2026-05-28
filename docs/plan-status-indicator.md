# 方案：对话气泡状态指示 + 思考折叠 + 发送打断

## 背景

当前后端 TurnRunner 在 RAG 检索、反思评估等阶段**无任何 SSE 事件输出**，前端在 metadata 到第一个 block 之间处于"盲等"状态。同时 thinking 事件只发空信号 `{text:"", time_ms:0}`，没有实际内容。用户在 AI 生成期间无法输入新消息。

目标：前端实时展示后端当前阶段，思考过程以折叠气泡呈现，用户可随时发送新消息（自动打断当前请求）。

---

## 一、后端改动

### 1.1 新增 `StatusEvent` SSE 事件

**文件**: `backend/app/agent_layer/contracts/sse_events.py`

```python
class StatusEvent(BaseModel):
    event: Literal["status"] = "status"
    phase: str           # "retrieving" | "reflecting" | "generating" | "compacting"
    message: str         # 人类可读中文提示
    detail: dict | None = None

    def to_sse_frame(self) -> str:
        payload = {"phase": self.phase, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return f"event: status\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
```

### 1.2 TurnRunner 各阶段 yield StatusEvent

**文件**: `backend/app/agent_layer/orchestration/turn_runner.py`

在 `run()` 方法中，以下位置插入 `yield StatusEvent(...)`：

| 位置 | phase | message | yield 在哪行之后 |
|------|-------|---------|-----------------|
| RAG 检索开始 | `"retrieving"` | `"正在查询文献库..."` | `if need_rag:` 之后（~L201） |
| 反思评估前 | `"reflecting"` | `"正在评估证据质量..."` | `judge_evidence()` 调用前（~L218） |
| 反思重检索 | `"retrieving"` | `"正在补充检索..."` | 反思循环中再次 `_retrieve()` 前 |
| 历史压缩 | `"compacting"` | `"正在压缩对话历史..."` | `compact_conversation()` 调用前 |
| LLM 生成前 | `"generating"` | `"正在生成回答..."` | `chat_stream()` 循环前（~L244） |

### 1.3 删除空 ThinkingEvent

当前 ThinkingEvent 只发 `{text: "", time_ms: 0}`，无实际内容。用 StatusEvent 替代其"信号"功能。如果 `thinking=true`，后端改为 yield `StatusEvent(phase="thinking", message="正在深度思考...")`，不再发空 ThinkingEvent。

> 注意：保留 ThinkingEvent 类定义不删，只是 TurnRunner 不再 yield 它。前端继续兼容，防止旧版本不兼容。

---

## 二、前端改动

### 2.1 SSE 客户端新增 `status` 事件处理

**文件**: `frontend/src/services/sse-client.ts`

- `AskStreamHandlers` 接口新增：`onStatus?: (phase: string, message: string) => void`
- switch 新增 `case 'status':` 解析并回调
- `parseStatusPayload()` 解析 `{phase, message}`

### 2.2 ConversationStore 新增 `phaseMessage` 状态

**文件**: `frontend/src/stores/conversation.ts`

- 新增 `phaseMessage = ref<string>('')` — 当前阶段提示文字
- `sendPrompt` 的 handlers 中新增 `onStatus` 回调，更新 `phaseMessage`
- `reset()` 时清空 `phaseMessage`
- `abortStreaming()` 时清空 `phaseMessage`

### 2.3 AIMessage 折叠状态指示器

**文件**: `frontend/src/components/AIMessage.vue`

替换现有 `thinking-section` 为**阶段指示器**，逻辑如下：

```
┌─────────────────────────────────┐
│ ▶ 正在查询文献库...    (1.2s)   │  ← 折叠态，点击可展开
└─────────────────────────────────┘
```

- **显示条件**：`isStreaming && phaseMessage`（流式中且有阶段消息）
- **折叠态**（默认）：显示 `phaseMessage` + 计时器
- **展开态**：显示全部已经历的阶段历史（可选，MVP 先不做）
- 当第一个 `block` 到达后，phaseMessage 被清空，指示器消失，内容正常展示

### 2.4 MessageList 传递 phaseMessage

**文件**: `frontend/src/components/MessageList.vue`

将 `phaseMessage` 从 store 传给正在流式输出的 AIMessage 组件。

### 2.5 InputBar 允许思考中发送

**文件**: `frontend/src/components/InputBar.vue`

**当前**：`isBusy` 时 textarea `disabled`
**改为**：`isBusy` 时 textarea **不禁用**，placeholder 改为 `"发送新消息将打断当前回答..."`

- `isBusy` 仍控制停止按钮的显示
- 发送逻辑不变（ChatView 的 `handleSend` 中先 abort 再 send）

### 2.6 ChatView 发送时自动打断

**文件**: `frontend/src/views/ChatView.vue`

`handleSend()` 开头增加：如果 `isBusy`，先调用 `store.abortStreaming()`。

```typescript
async function handleSend(promptText: string) {
  if (isBusy.value) {
    store.abortStreaming()
  }
  // ... 原有逻辑
}
```

---

## 三、完整 SSE 事件时序（改动后）

```
用户发送 → status: {phase: "retrieving", message: "正在查询文献库..."}
         → status: {phase: "reflecting", message: "正在评估证据质量..."}  (可选)
         → status: {phase: "generating", message: "正在生成回答..."}
         → block: {type: "heading", ...}
         → block: {type: "paragraph", ...}
         → block: {type: "list", ...}
         → sources: [...]
         → done: {}
```

前端 UI 对应：
```
[发送] → 折叠气泡 "正在查询文献库..." → "正在生成回答..." → 气泡消失 → 正常内容块流式出现
```

---

## 四、Demo 模式适配

**文件**: `frontend/src/demo/index.ts`

`mockSendPrompt` 中新增 status 阶段模拟：

```typescript
// Phase 0: Status events
schedule(() => handlers.onStatus?.('retrieving', '正在查询文献库...'), 200)
schedule(() => handlers.onStatus?.('generating', '正在生成回答...'), 1800)
// Phase 1: Thinking (optional)
// Phase 2: Blocks (existing)
```

---

## 五、文件清单

| 文件 | 改动 |
|------|------|
| `backend/app/agent_layer/contracts/sse_events.py` | 新增 `StatusEvent` 类 |
| `backend/app/agent_layer/orchestration/turn_runner.py` | 5处 yield StatusEvent，移除空 ThinkingEvent |
| `frontend/src/services/sse-client.ts` | 新增 `case 'status'` + `onStatus` 回调 |
| `frontend/src/stores/conversation.ts` | 新增 `phaseMessage` ref + `onStatus` handler |
| `frontend/src/components/AIMessage.vue` | 阶段指示器替代 thinking-section |
| `frontend/src/components/MessageList.vue` | 传递 phaseMessage |
| `frontend/src/components/InputBar.vue` | isBusy 时不禁用输入框 |
| `frontend/src/views/ChatView.vue` | handleSend 自动打断 |
| `frontend/src/demo/index.ts` | mock 新增 status 阶段 |

---

## 六、验证方式

1. 启动后端 `uv run python main.py`
2. 启动前端 `pnpm dev` + `?demo` 参数
3. Demo 模式：发送消息 → 看到折叠气泡 "正在查询文献库..." → 切换到 "正在生成回答..." → 气泡消失 → 内容流式出现
4. 真实后端：选中论文 → 发送 → 观察 SSE 事件时序是否正确
5. 打断测试：生成中发送新消息 → 旧的立即停止 → 新消息正常处理
