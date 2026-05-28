# runtime_chat_model 模块审计

## 对照模块

- 代码：`backend/app/agent_layer/runtime/chat_model.py`
- 相关设置：`backend/app/service_layer/config/settings.py`

## 结论

- 当前 `ChatModel` 只是一个全局 OpenAI 兼容客户端包装，还不是 request 级 Agent runtime 适配器。

## 发现

- [P0] 顶层直接 `from openai import AsyncOpenAI`，依赖缺失会在导入阶段直接炸。
  - 证据：`chat_model.py:7`
  - 实测：最小导入验证已复现 `ModuleNotFoundError: No module named 'openai'`

- [P1] `ChatModel` 只读取全局 `BackendSettings`，不会响应前端每次请求传来的 `model`。
  - 证据：`chat_model.py:13-27`

- [P1] 当前没有“thinking on/off”的运行时分支，也没有使用量统计输出。

- [P2] 当前实现假定单一 provider，和 `architecture.md` 中的 provider-neutral 基线不一致。

## 建议

1. 先把导入期硬依赖改成受控降级。
2. 让 `ChatModel` 支持 request 级 `model_name`。
3. 为后续 `thinking`、`usage`、多 provider 留出返回协议，不要继续把底层 SDK 返回结构漏到上层。
