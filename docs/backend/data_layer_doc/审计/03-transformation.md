# transformation 模块审计

## 对照模块
- 设计：`preprocessing/transformation/`
- 代码：
  - `backend/app/data_layer/preprocessing/transformation/pdf_converter.py`
  - `backend/app/data_layer/preprocessing/transformation/markitdown_adapter.py`

## 结论
- 模块具备基础文本提取能力，但元数据完整性和路由覆盖度与设计文档差距较大。

## 发现
- [P1] `metadata.page_count` 对 A/B/C/D 路由恒为 0。
  - 证据：`markitdown_adapter.py:44-49` 把 `page_count` 固定为 0；`pdf_converter.py:94-102` 直接把这个值写入 metadata。
  - 复现：真实中文样本转换成功，但 `probe_pdf()` 返回 38 页，而 `convert_pdf(..., route="A")` 的 metadata 里页数为 0。
  - 影响：后续 chunk anchor、报告、监控都会失真。

- [P0] Route E 没有按设计落地，当前实现是硬失败。
  - 证据：`pdf_converter.py:104-114`
  - 影响：设计文档承诺的扫描件链路完全不可用。

- [P1] metadata 明显缺字段，和设计文档不一致。
  - 证据：`pdf_converter.py:94-102` 只写了 `file_name/file_size/page_count/route/form_fields/tables/char_count`；没有 probe 数据、复杂度、降级信息、工具选择信息。
  - 影响：后续无法可靠生成 `structured.json`、`extraction_report.json`，现有旧测试也无法复用。

- [P1] Route C 不抽图片，和后续 VLM 路径对不上。
  - 证据：`pdf_converter.py:72-77` 只在 `route in ("B", "D")` 时抽图片；而 `transfer/pipeline.py:240-243` 会在 `Route.C` 时尝试走 VLM。
  - 影响：Route C 就算不报错，也不会给 VLM 提供输入。

- [P2] 图片提取依赖硬编码 Windows `poppler` 路径。
  - 证据：`pdf_converter.py:21-22,147-153`
  - 影响：跨机器和 CI 环境可移植性较差。

## 建议
1. 用 probe 结果补齐 `page_count`、复杂度、路由证据链。
2. Route E 不要以“不支持”结束；至少要接入 OCR stub 并明确降级输出。
3. Route C 与 B/D 一样，要么产页面图，要么彻底取消 VLM 依赖。

