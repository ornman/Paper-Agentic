# session_redis_runtime 模块测试设计

## 目标

- 验证 Redis 运行态的真实存储、TTL 和降级表现。

## 用例

1. `SES-U01`：`RedisConversationWindowStore.save_messages()` 后能真实读回消息列表。
2. `SES-U02`：`RedisEditorContextStore.put()` 后能真实读回完整上下文对象。
3. `SES-U03`：TTL 到期后，键必须自然失效。
4. `SES-I01`：Redis 不可用时，`build_redis_runtime()` 必须返回 NullStore 和 `unavailable` 健康状态。
5. `SES-C01`：`/api/v1/query` 接线后，验证：
   - 读取 recent window
   - 保存本轮窗口
   - 读取 editor context
   - 降级标记进入请求日志

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/agent_layer/session/test_redis_runtime.py`
  - `backend/tests/agent_layer/session/test_query_window_integration.py`
- 禁止用 fake redis 替代真实 Redis。
