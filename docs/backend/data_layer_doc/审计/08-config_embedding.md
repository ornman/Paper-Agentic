# config 与 embedding 模块审计

## 对照模块
- 设计：`storage/config/`、`storage/embedding/`
- 代码：
  - `backend/app/data_layer/storage/config/settings.py`
  - `backend/app/data_layer/storage/embedding/embedding_client.py`

## 结论
- 配置与 embedding 已经各自有代码，但并没有形成 data_layer 内部自洽的配置体系。

## 发现
- [P1] `.env` 加载路径指向 `backend/app/.env`，不是常规的 `backend/.env`。
  - 证据：`config/settings.py:97-106`
  - 影响：如果只在项目常规位置维护 `.env`，`load_config()` 会静默读不到。

- [P1] `DataLayerConfig` 与 `EmbeddingClient` 不在同一个配置体系里。
  - 证据：`config/settings.py:51-94` 定义的是 `DataLayerConfig`；`embedding_client.py:9-20` 依赖的是 `app.service_layer.config.settings.BackendSettings`。
  - 影响：data_layer 的配置模块就算改对了，embedding 也可能完全不生效。

- [P1] 环境变量命名不一致。
  - 证据：`config/settings.py:67,76` 使用 `SILICONFLOW_API_KEY`；`service_layer/config/settings.py:25-34` 使用 `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL`。
  - 影响：同一套环境变量不能同时驱动两边，后续排错成本高。

- [P2] `load_config()` 在仓库里几乎没有被实际消费。
  - 证据：代码搜索只命中了本模块定义和 `data_layer/__init__.py` 暴露。
  - 影响：配置模块当前更像占位代码。

## 建议
1. 确定一个唯一配置源，建议直接对齐 `BackendSettings`。
2. 如果保留 `DataLayerConfig`，至少要给 `EmbeddingClient`、VLM client 和 store 构造函数统一接入。

