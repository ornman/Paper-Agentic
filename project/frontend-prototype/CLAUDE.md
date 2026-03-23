# Claude 配置 - 前端原型项目

> **项目状态**: 已冻结（2026-03-23）
> **用途**: WPS 论文写作辅助工具的 UI 展示原型

---

## 项目定位

这是一个 **纯前端展示原型**，用于向客户演示界面效果：

- 不连接真实后端，所有数据都是模拟的
- 需要嵌入 WPS 侧边栏 TaskPane
- 界面风格：专业、简约、不像"AI 风格"

---

## 文档规范

### 目录结构

```
docs/
├── README.md                    # 文档入口
├── docs.db                      # SQLite 索引数据库
├── doc_index.py                 # 检索工具
├── 71-decisions/                # 已确认的关键决策记录
├── 72-archive/                  # 已过时的历史讨论
├── 80-open-questions/           # 尚未锁定的问题
├── 90-drafts/                   # 草案、模板
└── 99-reference/                # 外部参考、背景材料
```

### 新增文档流程

1. 判断文档类型：
   - **决策记录** → `71-decisions/`
   - **讨论稿** → `70-active-discussions/`（如有）
   - **草案** → `90-drafts/`
   - **参考资料** → `99-reference/`

2. 文档开头必须包含：
   ```markdown
   > **创建日期**: YYYY-MM-DD
   > **状态**: ...
   ```

3. 决策记录必须回答：
   - 背景是什么
   - 决策了什么
   - 为什么这样定
   - 影响哪些模块

### SQLite 索引

新增文档后，更新索引：

```bash
cd D:/同步/project/frontend-prototype/docs
python doc_index.py
```

或手动添加：

```python
from doc_index import add_document, add_decision

doc_id = add_document(
    title="文档标题",
    file_path="71-decisions/文件名.md",
    doc_type="decision",  # decision/discussion/draft/reference
    status="状态",
    tags=["标签1", "标签2"],
    summary="摘要"
)

add_decision(doc_id, "决策主题", "决策结果", "理由")
```

---

## 设计决策（已锁定）

| 决策 | 结论 | 理由 |
|------|------|------|
| 整体风格 | DeepSeek 简约风 | 用户偏好，专业感 |
| 主题系统 | 4 主题 + CSS 变量 | 适应不同偏好 |
| 图标策略 | SVG 内联 | 可控、无依赖 |
| 布局结构 | Tab 切换 | 节省 TaskPane 空间 |
| WPS 集成 | Vite `base: './'` | 本地路径兼容 |

详细决策记录见：`docs/71-decisions/决策-UI设计风格与主题系统.md`

---

## 快速启动

```bash
# 1. 启动 WPS 插件
cd D:/同步/.tools/wps-debug/test-plugin
wpsjs debug

# 2. 在 WPS 中点击：测试插件 → 论文助手 (UI原型)
```

---

## 修改后重新部署

```bash
cd D:/同步/project/frontend-prototype
pnpm build
rm -rf D:/同步/.tools/wps-debug/test-plugin/vue-app/*
cp -r dist/* D:/同步/.tools/wps-debug/test-plugin/vue-app/
# 重启 wpsjs debug
```

---

## 技术栈

- Vue 3 + TypeScript
- Vite（`base: './'`）
- Pinia 状态管理
- 纯 CSS 变量（主题切换）
- 内联 SVG 图标
