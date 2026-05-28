# response_answer_generator 模块审计

## 对照模块

- 代码：`backend/app/agent_layer/response/answer_generator.py`

## 结论

- 当前 `AnswerGenerator` 是“单轮检索 + 单轮生成”的回答器，不是设计文档里的 Agent 编排器。

## 发现

- [P0] 当前输出事件协议与前端 V2 不兼容。
  - 证据：`answer_generator.py:76-83`、`136-150`
  - 当前事件：`metadata / chunk / done / error`
  - 前端期望：`thinking / block / sources / done / error`

- [P1] 当前回答仍基于 `_SYSTEM_PROMPT` 中的 `[1][2]` 编号引用，而不是结构化 `ContentBlock`。
  - 证据：`answer_generator.py:20-30`

- [P1] 检索链没有 planning、没有 retrieval gating、没有 reflection。
  - 证据：`answer_generator.py:63-74` 直接 dense + sparse + RRF

- [P1] 上下文拼装只吃检索结果和最近数据库消息，不吃 `written_context / selection / compact 摘要`。
  - 证据：`answer_generator.py:122-134`

- [P1] `SourceCard` 关键字段不完整。
  - 证据：`answer_generator.py:101-115`
  - 问题：
    - `title` 写死成“未命名论文”
    - 没有 `file_path / local_path / import_time`

- [P1] 会话保存仍是纯文本消息保存，无法支撑前端 V2 回放。
  - 证据：`answer_generator.py:155-167`

## 建议

1. 不要继续在 `AnswerGenerator` 里叠加所有新逻辑。
2. 以 `TurnRunner` 为核心重拆：
   - planning
   - evidence loop
   - block streamer
   - source mapper
   - persistence
3. 先完成最小协议切换：
   - `thinking`
   - `block`
   - `sources`
   - `done`
   - `error`
