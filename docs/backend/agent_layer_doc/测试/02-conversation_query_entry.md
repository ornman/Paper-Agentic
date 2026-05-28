# conversation_query_entry 模块测试设计

## 目标

- 验证新旧入口迁移、历史列表接口和 SSE 事件顺序。

## 用例

1. `QRY-U01`：当前基线红灯，`POST /api/v1/query` 应先固定为 404，再在实现后转绿。
2. `QRY-U02`：当前基线红灯，`GET /api/v1/conversations/list?limit=50` 应先固定为 404，再在实现后转绿。
3. `QRY-I01`：`POST /api/v1/query` 最小成功链必须按顺序发出：
   - `thinking` 可选
   - 一个或多个 `block`
   - 一个 `sources`
   - 一个 `done`
4. `QRY-I02`：错误链必须发 `error` 事件，而不是中途断流无说明。
5. `QRY-I03`：`session_id` 为空时，后端必须自动创建会话并在事件流或响应上下文里可追踪。
6. `QRY-I04`：历史列表接口返回字段必须满足前端：
   - `session_id`
   - `msg_count`
   - `last_active`
   - `preview`

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/service_layer/query_api/test_query_route.py`
  - `backend/tests/service_layer/query_api/test_conversation_list.py`
- SSE 测试必须解析真实字节流，不允许直接调用内部生成器跳过 HTTP 层。
