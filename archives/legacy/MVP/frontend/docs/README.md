# 前端原型文档区

> **创建日期**: 2026-03-23
> **状态**: 冻结

这是 `WPS 论文写作辅助工具` 的 UI 原型文档区，记录设计决策、实现细节和参考资料。

---

## 文档索引

| 目录 | 用途 |
|------|------|
| `71-decisions/` | 已确认的关键决策记录 |
| `99-reference/` | 外部参考与背景材料 |

---

## 快速入口

- **设计决策**: [决策-UI设计风格与主题系统](./71-decisions/决策-UI设计风格与主题系统.md)
- **项目说明**: 见项目根目录 [README.md](../README.md)

---

## SQLite 检索

文档元数据存储在 `docs.db` 中，支持快速检索：

```bash
cd D:/同步/project/frontend-prototype/docs

# 搜索文档
python -c "
from doc_index import search_documents
results = search_documents('主题')
for r in results:
    print(f'{r[\"title\"]}: {r[\"summary\"]}')"

# 列出所有文档
python -c "
from doc_index import list_all_documents
for doc in list_all_documents():
    print(f'[{doc[\"doc_type\"]}] {doc[\"title\"]}')"
```

---

## 相关项目

- 主项目文档: `D:/同步/project/docs/`
- WPS 调试系统: `D:/同步/.tools/wps-debug/`
