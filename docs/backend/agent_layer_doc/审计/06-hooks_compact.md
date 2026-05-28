# hooks_compact 模块审计

## 对照模块

- 代码：`backend/app/agent_layer/hooks/compact.py`
- 设计基线：`docs/backend/architecture.md` 第 6.1.8

## 结论

- 当前 `compact` 只是一个可调用函数，不是运行时能力。

## 发现

- [P1] 当前只有“给一串消息 -> 返回摘要”能力，没有触发条件、没有上下文预算、没有重注入逻辑。
  - 证据：`compact.py:12-34`

- [P1] 当前实现没有保存摘要，也没有把摘要送回后续消息窗口。

- [P2] `compact` 成功或失败只记日志，不会进入请求级状态流。

## 建议

1. `compact` 不应独立漂浮，应挂到 `compact_check -> compacting` 状态。
2. 触发条件至少包含：
   - `context_tokens`
   - `remaining_tokens`
   - `remaining_ratio`
3. 摘要生成后要：
   - 保存长期事实
   - 更新 Redis `history_summary`
   - 进入下一轮上下文组装
