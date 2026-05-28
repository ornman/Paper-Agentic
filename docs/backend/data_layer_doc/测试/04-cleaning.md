# cleaning 模块测试设计

## 目标
- 验证 markdown 规整能力。
- 验证 cleaning 是否能作为真实链路的稳定中间产物，而不只是纯字符串处理函数。

## 用例
1. `CLEAN-U01`：控制字符、超长空行、重复字符、标题跳级、全角字符的定向单测。
2. `CLEAN-U02`：增加全角标点样例，要求测试能明确暴露当前“标点未半角化”的缺口。
3. `CLEAN-C01`：对真实 transformation 输出的 markdown 进行清洗，样本至少 2 中文 + 2 英文。
4. `CLEAN-C02`：修复后要求 cleaning 同时产出 structured payload；当前应先把“structured 缺失”固化为失败用例。

## ClaudeCode 执行要求
- 测试文件建议：`backend/tests/data_layer/cleaning/test_markdown_cleaner.py`
- 真实链路测试不要直接读取手工构造 markdown；必须至少复用 transformation 真实产物。

