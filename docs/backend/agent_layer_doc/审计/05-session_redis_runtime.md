# session_redis_runtime 模块审计

## 对照模块

- 代码：`backend/app/agent_layer/session/redis_runtime.py`

## 结论

- Redis 运行时包装层已经有基本形状，但实际只接上了 editor context 的“存”，没有接上真正的会话运行时。

## 发现

- [P1] `conversation_window` 的读写接口已实现，但当前对话主链没有使用。
  - 证据：`redis_runtime.py:32-48`

- [P1] `editor_context` 只存裸 `dict`，没有 schema 版本、时间戳、来源说明。
  - 证据：`redis_runtime.py:51-67`

- [P1] 运行时里没有 `frozen_snapshot`、`history_summary` 之类的正式键空间。

- [P2] Redis 不可用时会优雅降级到 NullStore，这是对的；但后续没有把降级信息传到请求级日志和 SSE。
  - 证据：`redis_runtime.py:70-88`

## 建议

1. Redis 至少分四类键：
   - `editor_context:{session_id}`
   - `conversation_window:{session_id}`
   - `frozen_snapshot:{request_id}`
   - `history_summary:{session_id}`
2. `editor_context` 和 `conversation_window` 都改为显式 schema。
3. 所有 NullStore 降级都要进入 `degraded_flags`。
