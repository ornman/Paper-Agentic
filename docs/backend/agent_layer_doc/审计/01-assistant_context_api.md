# assistant_context_api 模块审计

## 对照模块

- 代码：`backend/app/service_layer/api/assistant_routes.py`
- 相关存储：`backend/app/agent_layer/session/redis_runtime.py`

## 结论

- `written_context / selection` 已有“存得进去”的能力，但还没有“被回答链使用”的能力。

## 发现

- [P1] `PUT /assistant/written-context` 和 `PUT /assistant/selection` 只是在 Redis 上覆盖字段，没有版本、时间戳和快照 ID。
  - 证据：`assistant_routes.py:20-29`、`42-51`

- [P1] 读取接口是拆开的两个端点，缺少“同一时刻的 editor context 组合读取”。
  - 证据：`assistant_routes.py:32-39`、`54-61`

- [P0] 当前聊天入口没有读取 `editor_context_store`。
  - 证据：`conversation_routes.py:67-96` 初始化 `AnswerGenerator` 时未传 editor context；`answer_generator.py:52-169` 也没有任何 `written_context` / `selection` 读取逻辑。

- [P1] Redis 不可用时，接口直接返回 `degraded`，但不会把这个降级标记传到本轮对话请求。
  - 影响：前端和日志层无法知道“当前回答没有使用 editor context”。

## 建议

1. 增加统一读取对象，例如 `GET /assistant/context/{session_id}`。
2. editor context 存储对象至少带：
   - `session_id`
   - `written_context`
   - `selection`
   - `updated_at`
   - `snapshot_version`
3. 在 `/api/v1/query` 的 `snapshot_freeze` 阶段统一读取 editor context。
4. Redis 不可用时，把 `editor_context_unavailable` 写入本轮 `degraded_flags`。
