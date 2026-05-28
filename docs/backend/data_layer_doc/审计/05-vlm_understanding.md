# vlm_understanding 模块审计

## 对照模块
- 设计：`preprocessing/vlm_understanding/`
- 代码：
  - `backend/app/data_layer/preprocessing/vlm_understanding/vlm_processor.py`
  - `backend/app/data_layer/preprocessing/vlm_understanding/__init__.py`

## 结论
- 当前实现离设计文档要求差距较大，且存在明确的运行时断点。

## 发现
- [P0] 模块对外 API 不完整，调用方无法按预期使用。
  - 证据：`__init__.py:10-26` 只导出了类和工具函数，没有导出 `process_images`；`transfer/pipeline.py:260-263` 却依赖这个入口。
  - 影响：真实预处理链路在带图文档上必炸。

- [P1] 实际调用是串行 await，不是设计文档要求的逐图异步并发。
  - 证据：`vlm_processor.py:107-136` 在 `for analysis in analyses` 循环里直接 `await self._call_vlm(...)`。
  - 影响：多图论文会被线性放大耗时，和 transfer 的异步调度目标不一致。

- [P1] 临时 JSON 不是“每张图完成即落盘”，而是所有图片处理完后一次性写盘。
  - 证据：`vlm_processor.py:138-169`
  - 影响：中途失败时没有部分产物，不符合设计里的可恢复性。

- [P1] 没有生成 `parent_anchor`、`visual_blocks`，回填能力也只有正则替换 markdown 链接。
  - 证据：`vlm_processor.py:203-233`
  - 影响：设计文档里关于图片语义块、父子块召回的核心能力尚未落地。

- [P2] `analysis_route` 只有默认值，没有真实分类逻辑。
  - 证据：`vlm_processor.py:101-105`
  - 影响：兜底描述和后续分析分支都失去意义。

## 建议
1. 先补对外函数适配层，解除 orchestrator 的硬错误。
2. 再把处理改成真正的 async fan-out/fan-in，并在每图完成后刷临时 JSON。
3. 把 markdown 回填和 `visual_blocks` 生成拆成显式后处理步骤。

