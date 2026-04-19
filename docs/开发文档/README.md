# 论文助手 - 开发文档

> 学术写作助手（基于 RAG），前后端分离 + 本地部署

## 文档导航

| 阶段 | 目录 | 内容 |
|------|------|------|
| 需求 | [01-需求](./01-需求/) | PRD、用户故事、竞品调研、会议纪要 |
| 设计 | [02-设计](./02-设计/) | 架构、数据库、UI 设计、API 接口 |
| 开发 | [03-开发](./03-开发/) | 编码规范、[模块说明](./03-开发/模块说明/模块说明.md)、[开发日志](./03-开发/开发日志/开发日志.md) |
| 测试 | [04-测试](./04-测试/) | [测试用例](./04-测试/测试用例/测试用例.md)、[测试报告](./04-测试/测试报告/测试报告.md) |
| 部署 | [05-部署与运维](./05-部署与运维/) | 部署手册、运维流程、配置模板、故障记录 |
| 管理 | [06-项目管理](./06-项目管理/) | 会议纪要、进度报告、项目计划、模板 |

## V1 项目文档

V1 重构版的最新文档在项目目录内:

| 文档 | 路径 |
|------|------|
| 架构设计 | [project/V1_论文助手/docs/architecture/架构设计.md](../../project/V1_论文助手/docs/architecture/架构设计.md) |
| API 接口 | [project/V1_论文助手/docs/api/API接口文档.md](../../project/V1_论文助手/docs/api/API接口文档.md) |
| 开发指南 | [project/V1_论文助手/docs/development/开发指南.md](../../project/V1_论文助手/docs/development/开发指南.md) |

## 技术栈

- **后端**: FastAPI (Python 3.13)
- **前端**: Vue 3 + TypeScript + Vite
- **向量库**: Zvec（嵌入式，单 Collection + payload 过滤）
- **LLM/VLM**: Kimi Coding API + DeepSeek
- **Embedding**: 硅基流动 Qwen3-Embedding-8B (1536维)
- **关键词检索**: BM25 + jieba
- **PDF 解析**: MinerU API
- **部署**: WPS 插件

## 快速启动

详见 [开发指南](../../project/V1_论文助手/docs/development/开发指南.md)
