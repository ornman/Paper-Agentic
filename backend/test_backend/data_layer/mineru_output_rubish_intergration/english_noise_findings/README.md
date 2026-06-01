# 英文噪音发现测试数据

## 来源

基于 `Dev_Tools/clean_md_tool` 黑板扫描工具，用合成英文 markdown 测试 LLM 噪音检测能力。

## 测试模型

| 模型 | LLM 发现 | 启发式发现 | 说明 |
|------|----------|-----------|------|
| **nv-kimi** (moonshotai/kimi-k2.6) | 16 | 3 | 更全面，覆盖 5 种噪音类型 |
| **nv-minimax** (minimaxai/minimax-m2.7) | 7 | 3 | 较保守，漏检英文 OCR 空格和部分元数据 |

结论：**nv-kimi 更适合英文噪音检测**。

## 文件说明

| 文件 | 说明 |
|------|------|
| `test_input.md` | 合成英文 markdown 测试输入，包含多种典型噪音 |
| `kimi_findings.jsonl` | nv-kimi 扫描结果（22 条） |
| `minimax_findings.jsonl` | nv-minimax 扫描结果（10 条） |

## 噪音类型覆盖

### kimi 检测到的噪音

| 噪音类型 | 数量 | 示例 |
|----------|------|------|
| cover_metadata | 4 | `A R T I C L E  I N F O`、`Article history`、`Keywords:`、`Corresponding author` |
| watermark | 4 | `© 2023 Elsevier`、`Check for updates`、`Publisher's note`、`journal homepage` |
| ocr_spacing | 6 | `A B S T R A C T`、`I n t r o d u c t i o n`、`L i t e r a t u r e  R e v i e w` |
| table_noise | 1 | `<table>` HTML 标签 |
| header_footer | 1 | `第 5 页 共 24 页` |

## 对 markdown_cleaner.py 的扩展

基于黑板扫描发现的高频英文噪音，已将以下规则集成到生产清洗器：

### 新增模式常量

```python
# 英文学术元数据（_COVER_META_PATTERNS 扩展）
r"^©\s*\d{4}"                           # © 2023 Elsevier
r"^Article history"                      # Article history: Received ...
r"^Received\s+\d{1,2}\s+\w+\s+\d{4}"    # Received 27 May 2023
r"^Accepted\s+\d{1,2}\s+\w+\s+\d{4}"    # Accepted 11 October 2023
r"^Available online"                     # Available online 1 November 2023
r"^Keywords?\s*[:：]"                    # Keywords: digital twin
r"^A\s+R\s+T\s+I\s+C\s+L\s+E\s+I\s+N\s+F\s+O"
r"^A\s+B\s+S\s+T\s+R\s+A\s+C\s+T"
r"^Corresponding author"
r"^E-mail\s*[:：]"

# 英文页眉页脚（_EN_HEADER_FOOTER_PATTERNS）
r"^Check for updates$"
r"^Publisher'?s?\s+note"
r"^Contents lists? available"
r"^journal homepage"
r"^doi\s*:\s*10\."
r"^\d+\s*$"                              # 纯页码行

# HTML 表格标签（_HTML_TABLE_TAGS）
r"</?(?:table|tr|td|th|thead|tbody)\b[^>]*>"

# 英文标题逐字母空格（_EN_HEADING_SPACE_RE）
r"^(#{1,6}\s+)([A-Za-z](?:\s+[A-Za-z]){2,})\s*$"
```

### 新增清洗函数

| 函数 | 位置 | 作用 |
|------|------|------|
| `_strip_html_table_tags()` | Step 2 | 移除 `<table>/<tr>/<td>` 标签，保留文本 |
| `_remove_en_header_footer()` | Step 10 | 移除英文页眉页脚 |
| `_fix_heading_spaces_english()` | Step 13 | `## A B S T R A C T` → `## ABSTRACT` |

### 流水线变化

`clean_mineru_output()` 从 14 步扩展到 17 步。

## 验证命令

```bash
cd D:\真项目\论文助手\backend
uv run python -c "
from app.data_layer.preprocessing.cleaning import clean_mineru_output

# 英文封面元数据
raw = '© 2023 Elsevier\nArticle history: Received 27 May 2023\nKeywords: digital twin\n# Introduction\n正文'
r = clean_mineru_output(raw)
assert '© 2023' not in r.markdown
assert 'Keywords' not in r.markdown

# HTML 表格
raw2 = '<table><tr><td>A</td></tr></table>\n正文'
r2 = clean_mineru_output(raw2)
assert '<table>' not in r2.markdown

# 英文标题空格
raw3 = '## A B S T R A C T\n\n正文'
r3 = clean_mineru_output(raw3)
assert '## ABSTRACT' in r3.markdown

print('All checks passed')
"
```
