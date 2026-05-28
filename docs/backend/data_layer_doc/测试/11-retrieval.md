# retrieval 模块测试设计

## 目标
- 验证 dense/sparse/fusion 的结果协议、融合语义和真实检索效果。

## 用例
1. `RET-U01`：`DenseRetriever` 必须把 score 传出来；当前默认 0 的问题要先复现。
2. `RET-U02`：`SparseRetriever` 返回类型与 `rrf_fuse()` 入参兼容性测试，固定当前 `SparseResult` 解包错误。
3. `RET-U03`：`rrf_fuse()` 必须对 dense+sparse 的并集做融合，不能丢掉 sparse-only doc。
4. `RET-I01`：在 2 中文 + 2 英文真实论文完成 indexing 后，分别跑 dense、sparse、fusion 检索，断言三路都有结果且融合结果不少于任一路的有效独有召回。
5. `RET-I02`：构造 BM25 小语料库回归，确保单篇或双篇文档也能召回关键词命中。
6. `RET-C01`：若 agent 层要消费 fusion 结果，增加 `answer_generator` 的检索前半程集成测试，固定当前调用崩溃点。

## ClaudeCode 执行要求
- 测试文件建议：
  - `backend/tests/data_layer/retrieval/test_dense_retriever.py`
  - `backend/tests/data_layer/retrieval/test_sparse_retriever.py`
  - `backend/tests/data_layer/retrieval/test_rrf_fusion.py`
  - `backend/tests/data_layer/retrieval/test_retrieval_chain.py`
- 真检索回归必须在真实中英文论文上完成，不允许只对手工短文本做断言。

