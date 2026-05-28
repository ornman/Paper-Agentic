# hooks_compact 模块测试设计

## 目标

- 验证 compact 的触发条件、摘要写回和对话连续性。

## 用例

1. `CMP-U01`：空消息列表返回空摘要，不抛异常。
2. `CMP-U02`：真模型配置存在时，`compact_conversation()` 返回非空摘要。
3. `CMP-I01`：当 `remaining_ratio < 5%` 时，查询链必须触发 compact。
4. `CMP-I02`：compact 后，摘要必须被持久化并进入下一轮上下文组装。
5. `CMP-I03`：compact 成功或失败都必须进入结构化日志。
6. `CMP-C01`：构造长对话链，在第 N 轮触发 compact 后，再追问前文事实，回答仍能续上。

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/agent_layer/hooks/test_compact.py`
  - `backend/tests/agent_layer/hooks/test_compact_integration.py`
- `CMP-C01` 需要真模型；若未配置，标记 `blocked`。
