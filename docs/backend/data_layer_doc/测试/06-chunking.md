# chunking 模块测试设计

## 目标
- 验证 chunking 在真实清洗后文本上的切块质量和锚点完整性。

## 用例
1. `CHUNK-U01`：`estimate_tokens()`、句子切分、边界检测的基础单测。
2. `CHUNK-U02`：构造短文本和长文本，明确暴露当前“<128 token”和“>512 token”都可能出现的问题。
3. `CHUNK-C01`：对真实 cleaned markdown 跑 chunking，样本至少 2 中文 + 2 英文。
4. `CHUNK-C02`：修复后断言每个 chunk 满足 token 预算，且 anchor 至少具备 `page/block_type/heading_path/source_text_hash`。
5. `CHUNK-C03`：为超长段落样本验证 overlap 只在超长保护场景触发。

## ClaudeCode 执行要求
- 测试文件建议：`backend/tests/data_layer/chunking/test_semantic_chunker.py`
- 真链路测试必须复用 cleaning 的真实输出，不要直接用纯手工短字符串替代全部覆盖。

