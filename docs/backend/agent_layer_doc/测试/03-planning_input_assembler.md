# planning_input_assembler 模块测试设计

## 目标

- 固定当前导入红灯，并验证后续 snapshot / planning 的输入加权规则。

## 用例

1. `PLN-U01`：当前基线红灯，导入 `app.agent_layer.planning.input_assembler` 必须先复现 `SyntaxError`。
2. `PLN-U02`：修复后，`prompt-only` 场景必须产出 `used_inputs = ["prompt"]`。
3. `PLN-U03`：`written_context-only` 场景必须识别为“继续写”模式，不要求显式 prompt。
4. `PLN-U04`：`written_context + selection` 场景必须将 `selection` 识别为主焦点。
5. `PLN-U05`：`prompt + selection + written_context` 场景必须保留三源标识，不能拼成无标签大字符串。
6. `PLN-U06`：planning 输出必须包含 `need_rag` 和 `context_budget`。

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/agent_layer/planning/test_snapshot_builder.py`
  - `backend/tests/agent_layer/planning/test_retrieval_gate.py`
- `PLN-U01` 是必须先固化的红灯用例。
