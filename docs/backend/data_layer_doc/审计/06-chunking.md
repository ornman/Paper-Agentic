# chunking 模块审计

## 对照模块
- 设计：`preprocessing/chunking/`
- 代码：`backend/app/data_layer/preprocessing/chunking/semantic_chunker.py`

## 结论
- 现在更像“按句子粗切并补一个最小锚点”，还没有达到设计文档要求的语义切块与检索锚点能力。

## 发现
- [P1] `MIN_CHUNK_TOKENS=128` 和 `MAX_CHUNK_TOKENS=512` 没有对最终 chunk 生效。
  - 证据：`semantic_chunker.py:14-16` 定义了约束；`171-192` 只在累计句子 token 时判边界；`264-283` 再次拼接文本后重新估 token，但没有回查约束。
  - 复现：英文示例文本可生成 `token_count=73` 的过小 chunk；长文本示例可生成 `token_count=1151` 的超大 chunk。
  - 影响：后续 embedding 和召回窗口会不稳定。

- [P1] 设计文档要求的锚点字段大部分没有落地。
  - 证据：`Anchor` 虽有字段定义，但 `_create_chunk():268-276` 只填了 `anchor_id/source_file_path/char_start/char_end/paragraph_index/source_text_hash`。
  - 影响：`page/block_type/heading_path/parent_anchor_id` 等检索关键字段全部缺失。

- [P1] 超大块 fallback 和 overlap 策略没有实现。
  - 证据：全文件没有对应逻辑。
  - 影响：长段文本在真实论文上会直接突破 embedding 窗口预算。

- [P2] `embedding_func` 假定为同步函数，和实际异步 embedding client 不一致。
  - 证据：`semantic_chunker.py:137-141`
  - 影响：后续真接入 embedding client 时还要再包一层同步桥接。

## 建议
1. 在 `_create_chunk()` 后做一次最终 token 预算校验，不满足约束就二次切分。
2. 把 heading/page/block 元数据在 cleaning/transformation 阶段准备好，再注入 anchor。
3. 明确“语义切分”和“超长保护”是两套策略，不要只靠一句边界规则。

