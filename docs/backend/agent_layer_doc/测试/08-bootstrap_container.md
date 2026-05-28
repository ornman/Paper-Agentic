# bootstrap_container 模块测试设计

## 目标

- 验证容器装配、导入路径一致性和健康检查对 Agent 能力的表达。

## 用例

1. `BTS-U01`：当前基线红灯，导入 `AppContainer` 时先固定旧路径或依赖缺失导致的失败。
2. `BTS-U02`：修复后，`AppContainer.initialize()` 必须完成 SQLite / 向量索引 / BM25 / Redis 健康初始化。
3. `BTS-U03`：health 输出必须包含 Agent 维度能力状态：
   - `query_route_ready`
   - `editor_context_ready`
   - `structured_sse_ready`
   - `compact_ready`
4. `BTS-I01`：当 LLM 不可用但 Redis / SQLite 可用时，整体 health 应为 `degraded`，不是直接 `error`。
5. `BTS-I02`：当旧 data_layer import 路径全部收敛后，启动链要能在 `uv run` 下完整初始化。

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/service_layer/bootstrap/test_container.py`
  - `backend/tests/service_layer/bootstrap/test_health_agent_flags.py`
- `BTS-U01` 需要保留为回归用例，防止旧路径再次回流。
