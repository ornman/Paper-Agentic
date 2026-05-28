# retrieval 模块审计

## 对照模块
- 设计：`retrieval/dense/`、`retrieval/sparse/`、`retrieval/fusion/`
- 代码：
  - `backend/app/data_layer/retrieval/dense/vector_retriever.py`
  - `backend/app/data_layer/retrieval/sparse/keyword_retriever.py`
  - `backend/app/data_layer/retrieval/fusion/rrf_fusion.py`

## 结论
- 检索层当前最主要的问题不在“能不能调接口”，而在“结果是否正确”。

## 发现
- [P0] `SparseRetriever` 的返回类型和 `rrf_fuse()` 的入参协议不兼容。
  - 证据：`keyword_retriever.py:11-50` 返回 `SparseResult` dataclass；`rrf_fusion.py:20-23` 按 `(doc_id, score)` tuple 解包。
  - 复现：把 `SparseResult` 直接传给 `rrf_fuse()` 会报 `TypeError: cannot unpack non-iterable SparseResult object`。
  - 真实影响：`agent_layer/response/answer_generator.py:72-74` 就是按这个错误组合在调用。

- [P1] RRF 只保留 dense 结果集，BM25-only 文档会被静默丢掉。
  - 证据：`rrf_fusion.py:26-39` 只遍历 `dense_map` 构造 `fused_scores`。
  - 影响：稀疏检索无法补召回，只能给 dense 结果“加分”，达不到设计文档里的融合目的。

- [P1] `DenseRetriever` 的 `score` 字段永远是默认值 0。
  - 证据：`vector_retriever.py:11-17` 定义了 `score`；`55-61` 构造返回对象时没有写入 score；`vector_index.py:90-109` 查询时也没有请求 distance。
  - 影响：后续 rerank、调试和结果解释都拿不到向量相似度。

- [P1] BM25 在当前实现下对小语料库不可靠。
  - 证据：见 `审计/09-chroma_store.md` 中对 `KeywordIndex.query()` 的实测。
  - 影响：sparse 层本身就不稳，fusion 再正确也无从补救。

## 建议
1. 先统一 sparse 结果协议，再改 `rrf_fuse()` 为 dense+sparse 的并集融合。
2. 给 dense 查询显式带回 distance/score。
3. 在真实中英文样本上做检索回归，不要只停留在人工构造数据。

