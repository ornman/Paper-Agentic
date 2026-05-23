# 单元测试说明

## 测试文件

- `test_kimi_api.py` - Kimi API 连接测试

## 运行方式

### 1. 配置环境变量

确保 `project/MVP/backend/.env` 文件包含：

```env
KIMI_API_KEY=your_key_here
KIMI_BASE_URL=https://api.kimi.com/coding/v1
```

### 2. 运行测试

```bash
cd project/MVP/backend

# 直接运行测试文件
uv run python tests/test_kimi_api.py

# 或使用 pytest
uv run pytest tests/test_kimi_api.py -v
```

## 测试内容

### `test_kimi_vlm_connection`
测试 Kimi VLM API 连接（带图片）。

### `test_kimi_chat_connection`
测试 Kimi Chat API 连接（纯文本）。

### `test_user_agent_header`
验证 User-Agent 伪装是否正确：
```python
"User-Agent": "claude-code"  # 关键伪装
```

### `test_wrong_user_agent_fails`
测试错误的 User-Agent 会导致失败。

## Kimi API 请求头（参考 Novel_Agents）

```python
headers = {
    "x-api-key": settings.kimi_api_key,
    "Content-Type": "application/json",
    "anthropic-version": "2023-06-01",
    "User-Agent": "claude-code",  # 🔑 关键伪装
}
```

**来源**: `D:/真项目/Novel_Agents/.tools/rag/src/ingest/describer.py` (第 69-74 行)
