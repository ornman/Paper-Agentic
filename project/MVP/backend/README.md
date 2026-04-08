# 论文写作助手 - 后端服务

基于 FastAPI 的学术写作助手后端，提供 RAG 检索增强和 LLM 问答能力。

## 技术栈

- **框架**: FastAPI 0.115
- **LLM**: OpenAI 兼容协议
- **向量库**: ChromaDB
- **关键词检索**: rank_bm25 + jieba
- **数据库**: SQLite (SQLAlchemy ORM)

## 快速开始

### 1. 安装依赖

```bash
# 安装 uv（Python 包管理器）
pip install uv

# 同步依赖
uv sync
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入真实 API Key
nano .env
```

**必须配置的环境变量**：

```env
# LLM（必填）
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 硅基流动（后续 RAG 需要）
EMBEDDING_API_KEY=your_siliconflow_key
RERANK_API_KEY=your_siliconflow_key
```

### 3. 启动服务

```bash
# 方式 1: 使用 main.py
uv run python main.py

# 方式 2: 直接用 uvicorn（支持热重载）
uv run uvicorn app.main:app --reload
```

访问 http://localhost:8000/docs 查看 Swagger API 文档。

## 项目结构

```
backend/
├── app/
│   ├── api/v1/          # 路由层
│   │   └── routes/      # 各模块路由
│   ├── clients/         # 外部服务客户端
│   │   ├── llm_client.py
│   │   └── embedding_client.py
│   ├── repositories/    # 数据仓储层
│   │   └── sqlite_repo.py
│   ├── services/        # 业务逻辑层
│   │   └── qa_service.py
│   ├── models/          # 数据模型
│   │   ├── base.py      # 统一响应格式
│   │   ├── session.py   # 会话/消息模型
│   │   └── query.py     # 查询相关模型
│   ├── core/
│   │   └── config.py    # 配置管理
│   └── main.py          # FastAPI 应用
├── main.py              # 启动入口
├── pyproject.toml       # 项目配置
└── .env                 # 环境变量（不提交 Git）
```

## API 端点

### 健康检查

```bash
GET /api/v1/health/
```

### 会话管理

```bash
# 创建会话
POST /api/v1/session/
{"title": "新会话"}

# 获取会话列表
GET /api/v1/session/?page=1&page_size=20

# 获取会话详情
GET /api/v1/session/{session_id}

# 更新会话标题
PUT /api/v1/session/{session_id}/title
{"title": "论文讨论"}

# 删除会话
DELETE /api/v1/session/{session_id}

# 获取历史消息
GET /api/v1/session/{session_id}/history

# 清空历史
DELETE /api/v1/session/{session_id}/history
```

### 问答

```bash
# 流式问答（SSE）
POST /api/v1/query/ask
{
  "session_id": "xxx",
  "query": "什么是深度学习？",
  "context": {  # 可选
    "written_content": "...",
    "selected_text": "...",
    "prompt": "..."
  }
}

# 纯检索（非流式）
POST /api/v1/query/retrieve
{
  "query": "深度学习",
  "top_k": 10
}
```

### 配置

```bash
# 获取当前配置
GET /api/v1/config/

# 测试连接
POST /api/v1/config/test
{"test_type": "llm"}

# 获取推荐模型
GET /api/v1/config/models
```

## 开发指南

### 添加新路由

1. 在 `app/api/v1/routes/` 创建新文件
2. 在 `app/api/v1/router.py` 中注册

### 添加新服务

1. 在 `app/services/` 创建服务模块
2. 在路由中调用服务

### 数据库迁移

SQLite 会自动建表，无需迁移工具。如需修改表结构：

1. 编辑 `app/models/session.py`
2. 删除 `data/app.db`
3. 重启服务自动重建

## Docker 部署

```bash
# 构建镜像
docker build -t thesis-backend .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -e LLM_API_KEY=your_key \
  -v $(pwd)/data:/app/data \
  thesis-backend
```

## 测试

```bash
# 测试健康检查
curl http://localhost:8000/api/v1/health/

# 测试会话创建
curl -X POST http://localhost:8000/api/v1/session/ \
  -H 'Content-Type: application/json' \
  -d '{"title":"测试会话"}'
```

## License

MIT
