# MVP 前端设计文档

**日期**: 2026-03-25
**状态**: 已确认
**适用范围**: `D:/同步/project/MVP/frontend`

---

## 1. 产品定位

本前端不是通用聊天助手，而是**面向论文创作的 RAG 辅助插件**。

核心价值链：

1. 用户把自己收集的 PDF 文献导入知识库
2. 插件读取当前 WPS 文档写作上下文
3. 基于知识库与当前内容生成创作灵感/辅助建议
4. 每条结果必须提供可溯源来源

因此前端的核心不是“聊天感”，而是：

- 知识库可见
- 当前文档上下文可见
- 一键获取灵感
- 来源展示明确

---

## 2. 第一版范围

### 2.1 支持范围

第一版只支持：

- **WPS 文字**
- **右侧常驻侧边栏 TaskPane**
- **完整主界面骨架**
- **单会话消息流**
- **知识库一级入口**
- **灵感按钮闭环（场景 1）**

### 2.2 不在第一版范围内

第一版明确不做：

- 表格 / 演示场景
- 用户手动 prompt 主链路
- 圈选文本主链路
- 完整历史会话系统
- 语音输入
- 图片/附件解析
- 插入结果到文档
- 右键菜单“询问助手”
- 完整文献管理页

---

## 3. 设计方向

### 3.1 风格定位

前端风格采用：

- **Copilot 办公专业版**
- **模型中立**（不绑定 DeepSeek 品牌）
- **布局逻辑借鉴 DeepSeek / Claude**
- **容器形态遵循 WPS 桌面端右侧常驻侧边栏**

风格要求：

- 简约、大方、克制
- 像真正办公插件
- 不花哨
- 弱化“聊天助手”感
- 强化“基于文献库的创作工具”感

### 3.2 实现策略

采用**两者混合方案**：

- `D:/同步/project/MVP/frontend` 作为正式 Vue 应用壳
- `D:/同步/.tools/wps-debug` 作为 WPS 插件宿主桥接样板
- `D:/同步/.tools/rag` 作为 WPSJS / API / 小众概念优先知识源

也就是：

- **产品层归 `frontend/`**
- **宿主桥接层吸收 `.tools/wps-debug` 的可靠模式**

---

## 4. 整体信息架构

第一版前端主界面采用四段式结构：

1. **顶部导航栏**
2. **知识库状态层**
3. **中间内容层（空态 / 消息态）**
4. **底部固定操作层**

### 4.1 顶部导航栏

固定高度，始终可见：

- 左：历史入口按钮（第一版先做壳）
- 中：当前会话标题，默认 `新对话`
- 右：新建对话 / 收起按钮

### 4.2 知识库状态层

这是第一版一级核心入口，必须明显可见。

包含：

- 当前知识库状态：`可用 / 空库 / 导入中 / 导入失败`
- 已导入文献数量
- `导入 PDF` 按钮
- `查看文献` 入口壳
- 辅助提示：
  - 已接入知识库时：结果优先基于文献生成
  - 空库时：结果可能缺少来源支撑

### 4.3 中间内容层

分为空态和消息态。

#### 空态

展示：

- 中性助手标识
- 主标题：`今天想从哪一段开始推进？`
- 副标题：`结合当前文档与知识库，为你提供可溯源的创作辅助`
- 主按钮：`获取灵感`

#### 消息态

显示：

- 用户动作消息
- 助手回复消息
- 来源卡片列表

消息语义不是普通聊天，而是：

- 创作过程记录
- 基于文献的辅助建议

### 4.4 底部固定操作层

包含：

- 输入框（第一版保留，不作为主入口）
- 功能按钮壳：深度思考 / 智能搜索 / 附件 / 语音
- 主按钮：`获取灵感`

第一版真正打通的是：

- 获取灵感按钮

发送按钮和其他辅助按钮先做结构占位。

---

## 5. 侧边栏容器规范

### 5.1 容器形态

- WPS 窗口内右侧常驻 TaskPane
- 展开态宽度目标：**380px**
- 高度：自适应 WPS 可用高度
- 白底
- 左侧 1px 浅灰分隔线
- 无厚阴影
- 无全局浮层感

### 5.2 视觉层级

- 面板层级高于文档区
- 低于 WPS 顶部原生弹窗与菜单
- 与 WPS 原生面板风格统一

---

## 6. 消息与来源展示

### 6.1 消息区定位

消息区是交互载体，不是产品本体。

第一版保留完整单会话消息流，但强调：

- 创作辅助过程
- 文献来源支撑

### 6.2 回复结构

每条助手回复分三层：

1. 回复正文
2. 创作建议分点
3. **来源区域**

来源区域必须是回复的一部分，而不是附件式附属信息。

### 6.3 来源卡片内容

每条来源卡片最少包含：

- 文献标题
- 页码 / 段落
- 原文片段摘要
- 可点击展开更多

第一版必须让用户清楚感知到：

> 这条创作建议是有文献出处的。

---

## 7. 知识库导入交互

### 7.1 入口形式

知识库导入入口放在知识库状态层，采用：

- **路径输入框**
- **导入按钮**

第一版不做拖拽上传和文件选择器。

### 7.2 路径输入规则

用户手动输入 / 粘贴本地 PDF 路径。

占位符建议：

`输入 PDF 本地路径，例如 D:/论文库/xxx.pdf`

### 7.3 前端前置校验

点击导入时，前端先检查：

- 是否为空
- 是否像本地路径
- 是否以 `.pdf` 结尾

若失败，立即提示：

`输入有误，请填写正确的 PDF 本地路径`

### 7.4 后端二次校验

后端仍负责最终真实性校验：

- 是否存在
- 是否为文件
- 是否允许进入导入链路

所以原则是：

- 前端负责快速反馈
- 后端负责最终判断

### 7.5 导入状态反馈

导入流程的用户可见状态：

- 未输入
- 可提交
- 校验失败
- 导入中
- 导入成功
- 导入失败

第一版只做轻量反馈，不做复杂任务管理页。

---

## 8. WPS 交互层设计

### 8.1 前端四层架构

前端分为：

1. `wps-host` 层
2. `app-store` 层
3. `api-client` 层
4. `ui-components` 层

### 8.2 WPS Host 层职责

负责：

- 调 WPSJS API
- 轮询当前文档内容
- 读取文档标题
- 后续扩展读取选区文本

这一层不直接做 UI 逻辑。

### 8.3 第一版轮询策略

- 以轮询为主，事件监听为辅
- 轮询周期：**5 秒**
- 轮询对象：当前 WPS 文字文档正文缓存

轮询结果写入前端 store：

- `docTitle`
- `text`
- `updatedAt`
- `available`

前端不把轮询结果持续推送给后端，而是在用户点击动作时一次性发送。

---

## 9. 第一版真实闭环数据流

第一版只打通场景 1：

### 步骤 1
插件打开后，WPS host 开始轮询当前文档内容。

### 步骤 2
知识库状态层显示当前知识库状态与文献数量。

### 步骤 3
用户点击 `获取灵感`。

### 步骤 4
前端构造场景 1 请求：

```json
{
  "session_id": "<当前会话 id>",
  "text": "<当前轮询缓存>",
  "user_text": "",
  "user_prompt": "",
  "index_mode": "brute"
}
```

### 步骤 5
前端通过 `api-client` 调后端问答接口，接收 SSE。

### 步骤 6
消息区显示：

- 用户动作消息：例如 `基于当前写作内容获取灵感`
- 助手回复
- 来源卡片

### 步骤 7
用户可新建对话，回到空态。

---

## 10. 第一版前端状态机

### 10.1 宿主状态 `hostState`

- `booting`
- `ready`
- `no_document`
- `polling`
- `stale`
- `error`

### 10.2 知识库状态 `libraryState`

- `unavailable`
- `empty`
- `ready`
- `importing`
- `error`

### 10.3 会话状态 `conversationState`

- `idle`
- `requesting`
- `streaming`
- `done`
- `error`

### 10.4 UI 状态 `uiState`

- `sidebarExpanded`
- `historyDrawerOpen`
- `activeView`
- `toastMessage`

---

## 11. 组件结构

建议组件树：

```text
frontend/src/
├── app/
│   ├── AppShell.vue
│   └── routerless-entry.ts
├── components/
│   ├── layout/
│   │   ├── SidebarContainer.vue
│   │   ├── TopNavBar.vue
│   │   ├── KnowledgeBar.vue
│   │   └── BottomActionBar.vue
│   ├── conversation/
│   │   ├── EmptyState.vue
│   │   ├── MessageList.vue
│   │   ├── UserActionMessage.vue
│   │   ├── AssistantMessage.vue
│   │   └── SourceCardList.vue
│   ├── library/
│   │   ├── LibraryStatusBadge.vue
│   │   ├── LibrarySummary.vue
│   │   └── ImportPdfButton.vue
│   └── overlays/
│       └── HistoryDrawer.vue
├── stores/
│   ├── host.ts
│   ├── library.ts
│   ├── conversation.ts
│   └── ui.ts
├── services/
│   ├── wps-host.ts
│   ├── api-client.ts
│   └── sse-client.ts
├── types/
│   ├── host.ts
│   ├── conversation.ts
│   └── library.ts
└── styles/
    ├── tokens.css
    └── main.css
```

### 第一版真功能组件

- `AppShell.vue`
- `TopNavBar.vue`
- `KnowledgeBar.vue`
- `EmptyState.vue`
- `MessageList.vue`
- `AssistantMessage.vue`
- `SourceCardList.vue`
- `BottomActionBar.vue`

### 第一版只做壳

- `HistoryDrawer.vue`
- `LibrarySummary.vue`
- `ImportPdfButton.vue` 的复杂交互扩展部分

---

## 12. API 契约

### 12.1 获取知识库状态

```http
GET /api/v1/library/documents
```

前端用途：
- 计算文献数量
- 判断知识库状态

### 12.2 导入 PDF

```http
POST /api/v1/library/import
```

第一版请求体：

```json
{
  "file_path": "D:/xxx/论文.pdf",
  "index_mode": "brute"
}
```

第一版前端默认导入模式先固定成 `brute`。

### 12.3 获取灵感（场景 1）

```http
POST /api/v1/query/ask
```

第一版请求体固定为：

```json
{
  "session_id": "<当前会话 id>",
  "text": "<当前轮询缓存>",
  "user_text": "",
  "user_prompt": "",
  "index_mode": "brute"
}
```

---

## 13. SSE 事件消费

第一版前端重点消费：

- `chunk`
- `sources`
- `done`
- `error`

### 13.1 事件含义

- `chunk`：追加助手回复正文
- `sources`：写入来源卡片
- `done`：结束加载态
- `error`：进入失败态并给出提示

`retrieval_start` / `retrieval_done` 可先只做内部状态，不强展示。

---

## 14. WPS 宿主桥接策略

### 14.1 正式 UI 工程

正式 UI 仍放在：

- `D:/同步/project/MVP/frontend`

### 14.2 宿主桥接样板来源

从：

- `D:/同步/.tools/wps-debug`

迁移吸收这些已验证能力：

- `GetUrlPath()`
- `Application.CreateTaskPane(...)`
- `DockPosition = 2`
- `taskPane.Width = 400` 的可行模式
- `wps.WpsApplication()`
- `Selection.Text` 读取思路
- Playwright / 调试链路经验

### 14.3 第一版工程边界

建议在正式前端工程内增设：

```text
frontend/
├── src/
├── public/
├── wps-plugin/
│   ├── main.js
│   ├── ribbon.xml
│   ├── taskpane.html
│   └── bridge/
└── ...
```

也就是：

- Vue 应用归 `src/`
- WPS 插件壳归 `wps-plugin/`
- 不把 `.tools/wps-debug` 直接当正式产品工程

---

## 15. 第一版实现顺序

### 步骤 1
迁移 WPS 宿主桥接层：
- Ribbon
- TaskPane
- `wps.WpsApplication()`
- `GetUrlPath()`

### 步骤 2
搭主界面骨架：
- 顶部栏
- 知识库状态层
- 空态
- 底部灵感区

### 步骤 3
接入 WPS 轮询：
- 每 5 秒轮询当前文档内容
- store 更新

### 步骤 4
接知识库状态与导入：
- `GET /library/documents`
- `POST /library/import`
- 路径输入校验

### 步骤 5
接灵感闭环：
- `POST /query/ask`
- SSE 回复
- 来源卡片

### 步骤 6
补历史抽屉壳：
- 开关
- 面板结构
- 不接真实历史数据

### 步骤 7
Playwright 全流程测试：
1. 打开插件
2. 显示右侧栏
3. 轮询到文档内容
4. 错误路径提示输入有误
5. 正确路径导入成功
6. 点击获取灵感，收到回复与来源

---

## 16. 第一版最小真实闭环

第一版真正要跑通的体验是：

1. 在 WPS 文字里打开右侧侧边栏
2. 看到：
   - 顶部导航
   - 知识库状态条
   - 空态引导
   - 底部获取灵感区
3. 插件自动轮询当前文档内容
4. 用户输入 PDF 路径并导入
5. 知识库状态更新为可用
6. 用户点击 `获取灵感`
7. 流式显示助手回复
8. 回复下方展示来源卡片
9. 用户可新建对话回到空态

如果这条链路成立，前端第一版就算真正跑通。

---

## 17. 参考资料说明

### 17.1 WPS 桌面端布局稿

用户提供的桌面端右侧侧边栏描述是当前主要容器规范来源，用于定义：

- 常驻右侧侧边栏形态
- 380px 目标宽度
- 顶部/中部/底部三段布局
- 历史会话抽屉
- 办公插件化视觉风格

### 17.2 移动端 DeepSeek 稿

用户提供的移动端稿仅用于参考：

- 空态层级
- 顶部导航组织
- 历史会话分组逻辑
- 对话结构

不直接照搬其物理尺寸和移动端交互比例。

### 17.3 成功样板

- `D:/同步/.tools/wps-debug`
  - 已证明 TaskPane、Ribbon、WPS API、Playwright 调试链路可用

### 17.4 小众 API 与文档知识源

- `D:/同步/.tools/rag`
  - 遇到 WPSJS / 插件 API / 社区案例问题时优先检索

---

## 18. 最终结论

前端第一版正式共识如下：

- 这是**论文创作 RAG 辅助插件**，不是通用聊天助手
- **知识库是一级核心入口**
- 第一版只支持 **WPS 文字**
- 采用 **WPS 右侧常驻侧边栏**
- 风格为 **Copilot 办公专业版**
- 模型中立，只借鉴 DeepSeek / Claude 的布局逻辑
- 正式 UI 基于 `frontend/`，宿主桥接吸收 `.tools/wps-debug`
- 第一版闭环是：
  - 路径导入 PDF
  - 知识库状态可见
  - 轮询当前文档
  - 点击获取灵感
  - 返回带来源建议

这份文档是当前前端设计的唯一有效结果，后续实施以此为准。
