# transformation 模块测试设计

## 目标
- 验证真实 PDF 转 markdown、metadata、图片产物的正确性。
- 对不同 route 的分支行为做真实样本验证。

## 用例
1. `TRANS-U01`：`ConversionResult` 数据结构契约测试。
2. `TRANS-I01`：不存在文件应返回 `success=False`，且有可读错误信息。
3. `TRANS-C01`：中文 Route A + 英文 Route A 真实样本转换后，断言 markdown 非空，`metadata.page_count == probe.page_count`，且 metadata 含 route、complexity、probe 摘要。
4. `TRANS-C02`：Route B 真实样本转换后，断言 `images` 非空、每个图片路径存在、页码为 1-based。
5. `TRANS-C03`：Route C 真实样本转换后，断言表单/表格元数据可用，且若后续 VLM 依赖图片，则图片输入也必须准备好。
6. `TRANS-C04`：Route E 真实样本必须进入 OCR/降级链路；当前“不支持”应先被测试固定为失败基线。

## ClaudeCode 执行要求
- 测试文件建议：`backend/tests/data_layer/transformation/test_pdf_converter.py`
- 输出 artifacts 建议保存在 `backend/tests/_artifacts/data_layer/transformation/<sample_name>/`
- 真实样本至少覆盖中英文各 2 份，不允许只用中文样本得出结论。

