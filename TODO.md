# TODO — 论文助手

## 前端 WPS 集成（主要短板）

后端 REST 端点已就绪（`/assistant/written-context`、`/assistant/selection`、`/assistant/snapshot`），
实际短板在前端侧。

### WPS JS API 调用

- [ ] **选区事件绑定不稳定** — `ActiveWindow.SelectionChange = handler` 是直接赋值，
  WPS 多窗口/文档切换时会丢失绑定。需要事件注册+注销机制，或改用定时轮询兜底。
  > 代码：`frontend/src/composables/wps.ts:224-241`

- [ ] **已写内容获取缺失** — 当前只有 `useWPSSelection`（获取选中文本），没有
  `useWPSWrittenContext`（获取文档全文或指定区域内容）。后端 `/assistant/written-context`
  端点已就绪，前端缺对应的采集逻辑。
  > WPS API 参考：`ActiveDocument.Content.Text` 或 `Range(start, end).Text`

- [ ] **选区位置信息不完整** — `SelectionInfo.start/end` 固定返回 `0/text.length`，
  没有取真实文档偏移量。影响后端引用定位精度。
  > 代码：`frontend/src/composables/wps.ts:103-105`

### 插件生命周期管理

- [ ] **无卸载/重载机制** — `OnAddinLoad` 只记日志，没有状态初始化。
  插件热更新或 WPS 崩溃恢复后，Vue 应用状态可能与 WPS 宿主不同步。

- [ ] **TaskPane 无关闭回调** — `OnOpenPane` 打开 TaskPane 后没有监听关闭事件，
  用户手动关闭面板后 polling/selection binding 不会自动停止。
  > 代码：`frontend/wps-plugin/main.js:59-68`

- [ ] **错误恢复缺失** — `main.js` 里 `OnOpenPane` 失败直接 `alert`，
  没有重试或降级方案（比如降级到浏览器模式）。

### 内容同步策略

- [ ] **轮询 vs 事件驱动未定** — `useWPSPolling` 每 5 秒轮询选区，
  `useWPSSelectionChange` 用事件驱动。两者并存但没有统一策略，需要决定主路径。

- [ ] **增量同步未实现** — 当前每次都读全量选区文本推给后端，
  应该做 diff 只推变更部分，减少网络开销。

- [ ] **防抖/节流缺失** — 选区变化频繁触发时没有防抖，可能导致大量无意义的 API 调用。

### 测试覆盖

- [ ] **WPS 模拟环境** — 无法在 CI 中测试 WPS JS API（需要 WPS 宿主），
  至少需要 mock 层覆盖 `useWPS*` composable 的逻辑分支。
