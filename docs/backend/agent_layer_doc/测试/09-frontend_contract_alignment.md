# frontend_contract_alignment 模块测试设计

## 目标

- 从前端已存在的真实调用方式反推后端契约，保证联调不是“看起来差不多”。

## 用例

1. `FED-I01`：用前端当前 payload 直接请求 `/api/v1/query`：
   - `session_id`
   - `prompt`
   - `paper_ids`
   - `enable_rag`
   - `model`
   - `thinking`
   后端必须能正常处理。
2. `FED-I02`：`thinking=true` 时，必须至少收到一个 `thinking` 事件或明确返回“不支持 thinking”的降级标记。
3. `FED-I03`：回答结束时的 `sources` 必须能满足前端引用预览：
   - `id`
   - `title`
   - `page`
   - `content`
   - `import_time`
4. `FED-I04`：历史列表接口返回必须满足 `SettingsView` 当前字段。
5. `FED-I05`：`/api/v1/models` 必须能返回真实模型列表，或在未实现前固定为红灯。
6. `FED-C01`：在真实论文索引上发一个 query，拿到的 SSE 事件按前端解析器顺序消费后，不得出现未知事件类型。

## ClaudeCode 执行要求

- 测试文件建议：
  - `backend/tests/integration/test_frontend_query_contract.py`
  - `backend/tests/integration/test_frontend_history_contract.py`
  - `backend/tests/integration/test_models_contract.py`
- `FED-C01` 建议直接复用前端的 SSE 解析规则或复制同构解析器，避免“后端自证自己正确”。
