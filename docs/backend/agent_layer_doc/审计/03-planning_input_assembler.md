# planning_input_assembler 模块审计

## 对照模块

- 代码：`backend/app/agent_layer/planning/input_assembler.py`
- 设计基线：`docs/backend/architecture.md` 第 6.1.3、6.1.4

## 结论

- 当前 `planning` 还不是规划模块，只是几个字符串拼接和截断辅助函数。

## 发现

- [P0] 文件当前有语法错误，直接阻断 `AnswerGenerator` 导入。
  - 证据：`input_assembler.py:27-33`
  - 实测：最小导入验证已复现 `SyntaxError: unterminated triple-quoted string literal`

- [P1] `assemble_query()` 只是把 `prompt / selection / written_context` 顺序拼接，没有加权、没有模式判断、没有 token 预算。
  - 证据：`input_assembler.py:11-24`

- [P1] 当前模块没有任何“冻结快照”对象，也没有 retrieval gating。
  - 影响：无法表达“本轮使用了哪些输入源”，也无法回答“为什么这轮不检索”。

- [P2] `sanitize_title()`、`truncate_snippet()` 这类工具函数仍然有价值，但不应该继续承担 planning 名义。

## 建议

1. 把当前文件拆成：
   - `snapshot_builder.py`
   - `retrieval_gate.py`
   - `title_builder.py`
2. 先修语法错误，再把“字符串拼接器”升级成 `FrozenTurnSnapshot` 构造器。
3. 规划阶段至少产出：
   - `used_inputs`
   - `need_rag`
   - `query_intent`
   - `context_budget`
