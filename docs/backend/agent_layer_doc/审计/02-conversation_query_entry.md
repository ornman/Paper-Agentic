# conversation_query_entry 模块审计

## 对照模块

- 代码：
  - `backend/app/service_layer/api/conversation_routes.py`
  - `backend/app/service_layer/schemas/conversation.py`
  - `backend/app/service_layer/api/router.py`
- 前端调用：
  - `frontend/src/services/sse-client.ts`
  - `frontend/src/views/SettingsView.vue`

## 结论

- 当前 service 层入口还是 V1 风格；前端 V2 的对话接口和历史接口都没有完全对上。

## 发现

- [P0] 后端没有 `POST /api/v1/query`。
  - 证据：`router.py:10-14` 仅注册 `health / library / conversations / assistant`；`conversation_routes.py:67-96` 当前入口是 `/conversations/chat`。

- [P0] 当前 `ChatRequest` 只有 `session_id / message / paper_ids`，缺少前端 V2 已发送的 `prompt / selection / draft / enable_rag / model / thinking`。
  - 证据：`schemas/conversation.py:8-11`

- [P1] 历史列表接口路径不一致。
  - 前端：`SettingsView.vue:137`
  - 后端：`conversation_routes.py:24-28`

- [P1] 当前消息回放模型只适合纯文本消息，`ConversationMessageOut` 只有 `content` 和可选 `sources_json`。
  - 证据：`schemas/conversation.py:27-32`
  - 影响：后续若保存结构化 `blocks`，这个 schema 不够用。

## 建议

1. 新建正式入口 `POST /api/v1/query`，不要继续把新协议压在 `/conversations/chat` 上。
2. `/conversations` 只负责历史会话管理，不负责当前问答。
3. 增加历史列表兼容路由：
   - `GET /api/v1/conversations`
   - 或补一个 `GET /api/v1/conversations/list`
4. 会话回放返回结构要升级为：
   - `user.content`
   - `assistant.thinking`
   - `assistant.blocks`
   - `assistant.sources`
