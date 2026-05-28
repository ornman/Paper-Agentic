# UI 问题修复清单

> 生成时间: 2026-05-28
> 来源: 用户截图反馈
> 状态: **全部已修复**（2026-05-29 验证）

## 问题列表

### P0 — 阻塞体验
1. **文献库空白** — demo 数据没有自动加载，用户打开 `app.html` 时看不到任何数据
2. **引用来源重复** — AIMessage 内部和 SourcePanel 底部面板同时显示来源，视觉上是重复的

### P1 — 核心功能缺失
3. **引用来源点不了** — 点击引用 badge 没有响应（demo 模式下无真实文件路径）
4. **AI 回复缺少行内引用** — 正文中没有 [1][2] 标记，只在底部有 badge
5. **文献库没有子数据** — 只显示标题，没有 chunk 数、页数、导入日期等元信息
6. **文献库没有全选** — 没有全选复选框

### P2 — 体验优化
7. **上传没有进度条** — store 有进度数据但没有 UI 渲染
8. **搜索功能不可见** — LibraryPanel 有搜索框但只有在 papers > 0 时显示，初始状态不可见

## 修复方案

| # | 修复 | 涉及文件 |
|---|------|----------|
| 1 | 自动检测后端，不可用时自动 seed demo 数据 | `ChatView.vue` |
| 2 | 去掉 SourcePanel 或合并到 AIMessage | `ChatView.vue`, `SourcePanel.vue` |
| 3 | 点击引用 badge 弹出摘要浮层 | `ChatView.vue` |
| 4 | AI 回复正文中插入 [1][2] 行内引用 | `AIMessage.vue` |
| 5 | LibraryPanel 显示元数据（页数、chunk数、日期） | `LibraryPanel.vue` |
| 6 | 添加全选复选框 | `LibraryPanel.vue` |
| 7 | 上传进度条 UI | 新建或修改 `LibraryPanel.vue` |
| 8 | 确保搜索框始终可见 | `LibraryPanel.vue` |
