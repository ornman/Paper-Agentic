# bootstrap_container 模块审计

## 对照模块

- 代码：`backend/app/service_layer/bootstrap/container.py`

## 结论

- 当前容器层是 Agent 层重构的外部阻断之一，因为它仍在连旧 data_layer 路径。

## 发现

- [P0] 容器 import 的 `app.data_layer.indexing.* / storage.* / normalization.*` 与当前 `backend/app/data_layer` 目录不一致。
  - 证据：`container.py:7-18`

- [P1] `AppContainer` 当前只装配了一个全局 `chat_model`，不适合 request 级模型选择。
  - 证据：`container.py:26-40`

- [P1] 容器 health 只看基础组件是否存在，不看“query route 是否可用”“editor context 是否接线”“compact 是否可用”。
  - 证据：`container.py:61-77`

## 建议

1. 先把 data_layer 接口收敛到当前活动目录。
2. Agent 层需要的是端口注入，不是继续依赖旧目录实现细节。
3. 健康检查增加 Agent 维度：
   - `query_route_ready`
   - `editor_context_ready`
   - `structured_sse_ready`
   - `compact_ready`
