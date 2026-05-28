# response_answer_generator 模块测试设计

## 目标

- 验证回答链从检索结果到结构化 block / sources 的转换。

## 用例

1. `RSP-U01`：当前基线红灯，`AnswerGenerator` 导入应先因 `input_assembler.py` 报错而失败。
2. `RSP-U02`：修复后，空输入必须发 `error` 事件。
3. `RSP-I01`：有检索结果时，必须输出至少一个 `block`，不能只输出 `chunk` 文本。
4. `RSP-I02`：回答结束后必须输出一次完整 `sources`，其中每个 `source.id` 都能被回答里的 citation 引用。
5. `RSP-I03`：`SourceCard` 必须带 `title / page / content / file_path / import_time`，缺字段即失败。
6. `RSP-I04`：当 `enable_rag = false` 时，必须跳过检索分支并给出无来源回答或空来源数组。
7. `RSP-C01`：基于真实中英文论文索引，提一个可回答问题，断言回答链真实引用了命中文献。

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/agent_layer/response/test_answer_generator_contract.py`
  - `backend/tests/agent_layer/response/test_source_mapper.py`
  - `backend/tests/agent_layer/response/test_real_query_chain.py`
- `RSP-C01` 必须使用真实索引和真实 LLM；若 LLM 未配置，记为 `blocked`。
