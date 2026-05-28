# config 与 embedding 模块测试设计

## 目标
- 验证配置优先级、`.env` 位置、embedding 真调用以及 batch/concurrency 行为。

## 用例
1. `CONF-U01`：环境变量优先级测试，要求 `env > .env > default`。
2. `CONF-U02`：显式验证 `.env` 应从 `backend/.env` 读取，当前错误路径要先复现。
3. `EMB-U01`：batch 切分、空输入、重试次数和结果顺序的单测。
4. `EMB-C01`：若 embedding API 已配置，取真实中文/英文清洗后 chunk 各若干条，跑真实 embedding，验证向量数量、维度、返回顺序。
5. `EMB-C02`：在并发场景下验证 semaphore 生效，不出现结果丢失。

## ClaudeCode 执行要求
- 测试文件建议：
  - `backend/tests/data_layer/config/test_settings.py`
  - `backend/tests/data_layer/embedding/test_embedding_client.py`
- 若真实 embedding API 未配置，`EMB-C01/C02` 必须输出 `blocked`，不能用 stub 假装通过。

