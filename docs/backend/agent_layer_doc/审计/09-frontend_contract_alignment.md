# frontend_contract_alignment 模块审计

## 对照模块

- 前端：
  - `frontend/src/services/sse-client.ts`
  - `frontend/src/stores/conversation.ts`
  - `frontend/src/views/SettingsView.vue`
  - `frontend/src/services/model-api.ts`
  - `frontend/src/composables/wps.ts`
- 后端：
  - `backend/app/service_layer/api/conversation_routes.py`
  - `backend/app/service_layer/api/assistant_routes.py`

## 结论

- 当前前后端不是“字段差一点”，而是“协议代际不同”。

## 发现

- [P0] 前端正式问答入口已经切到 `/api/v1/query`。
  - 证据：`sse-client.ts:39`

- [P0] 前端当前只消费 `thinking / block / sources / done / error`。
  - 证据：`sse-client.ts:183-190` 及其后续 switch 分支

- [P1] 前端 store 当前真实发送的字段是：
  - `prompt`
  - `paper_ids`
  - `enable_rag`
  - `model`
  - `thinking`
  - 证据：`conversation.ts:125-132`

- [P1] `AskRequestPayload` 类型里虽然有 `selection / draft`，但 store 当前没有传。
  - 证据：`sse-client.ts:8-18`、`conversation.ts:125-132`

- [P1] WPS 当前只是把选中文字自动写回输入框，还没有走 `/assistant/selection`。
  - 证据：`wps.ts:140-148`

- [P1] 前端会调 `/api/v1/models` 拉模型列表，但当前后端没有这个路由。
  - 证据：`model-api.ts:17-25`

- [P1] 前端设置页历史列表走 `/api/v1/conversations/list`，后端没有这个路径。
  - 证据：`SettingsView.vue:134-139`

- [P2] 前端当前没有消费 `metadata` 事件。
  - 影响：若后端需要发 token/降级信息，只能作为附加观测事件，不能指望当前 UI 展示。

## 建议

1. 先冻结正式接口：
   - `POST /api/v1/query`
   - `GET /api/v1/conversations/list`
   - `POST /api/v1/models`
2. 后端先以“前端当前真实发送的字段”作为第一阶段基线。
3. `selection / written_context` 接口仍然要保留，但落地顺序排在 `/query` 主链之后。
