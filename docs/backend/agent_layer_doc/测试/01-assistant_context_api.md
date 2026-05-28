# assistant_context_api 模块测试设计

## 目标

- 验证 `written_context / selection` 的真实存取、降级行为和后续快照消费前提。

## 用例

1. `CTX-U01`：Redis 可用时，`PUT /api/v1/assistant/written-context` 后 `GET` 必须读回同值。
2. `CTX-U02`：Redis 可用时，`PUT /api/v1/assistant/selection` 后 `GET` 必须读回同值。
3. `CTX-U03`：连续先写 `written_context` 再写 `selection`，不得发生字段覆盖丢失。
4. `CTX-I01`：Redis 不可用时，两个 `PUT` 都必须返回 `degraded`，且 `GET` 返回空上下文，不抛 500。
5. `CTX-C01`：在 `/api/v1/query` 接线后，先写 editor context，再发 query，验证本轮快照里确实使用了该上下文。

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/agent_layer/test_assistant_context_api.py`
- `CTX-C01` 必须走真实 Redis，不允许 monkeypatch 存储对象。
