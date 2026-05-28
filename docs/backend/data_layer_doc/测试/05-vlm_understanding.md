# vlm_understanding 模块测试设计

## 目标
- 验证图片语义理解模块的 API 契约、重试逻辑和真实图片处理链路。

## 用例
1. `VLM-U01`：模块对外 API 测试，要求 `transfer` 能拿到可调用入口；当前应先复现导入失败。
2. `VLM-U02`：`_encode_image()`、fallback 描述、重试次数、错误状态的契约测试。
3. `VLM-I01`：mock VLM API，验证每张图片的状态变化、attempt_count、临时 JSON 写入。
4. `VLM-C01`：若 `VLM_API_KEY`/`VLM_BASE_URL` 已配置，选 1 份中文含图样本 + 1 份英文含图样本，真实提图后跑 VLM，验证描述非空。
5. `VLM-C02`：修复后验证 markdown 回填、`visual_blocks`、`parent_anchor` 生成。

## ClaudeCode 执行要求
- 测试文件建议：`backend/tests/data_layer/vlm/test_vlm_processor.py`
- 若真实 API 未配置，`VLM-C01/C02` 必须标记为 `blocked` 并输出阻塞原因，不得用 mock 代替“链路通过”。

