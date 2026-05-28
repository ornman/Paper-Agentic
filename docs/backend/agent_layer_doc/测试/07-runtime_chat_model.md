# runtime_chat_model 模块测试设计

## 目标

- 验证模型运行时初始化、请求级模型切换和缺依赖降级。

## 用例

1. `LLM-U01`：当前基线红灯，缺少 `openai` 包时导入 `ChatModel` 会失败；先固化此失败。
2. `LLM-U02`：修复后，缺少 SDK 时应用启动不得直接崩溃，必须暴露 `unavailable` 健康状态。
3. `LLM-U03`：同一进程内两次 query 指定不同 `model`，运行时必须按请求选择模型。
4. `LLM-I01`：流式回答时必须真实产生 token 流，而不是一次性整段返回。
5. `LLM-I02`：当模型端报错时，查询链必须发 `error` 事件，不得静默断流。

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/agent_layer/runtime/test_chat_model_boot.py`
  - `backend/tests/agent_layer/runtime/test_chat_model_request_level.py`
- 若使用真实 provider，请记录模型名、首 token 延迟和总耗时到 artifacts。
