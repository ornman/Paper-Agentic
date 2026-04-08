"""
文档索引管理工具

用于管理和检索项目设计文档的元数据。
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# 数据库路径
DB_PATH = Path(__file__).parent / "docs.db"

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_date TEXT NOT NULL,
            tags TEXT,
            summary TEXT,
            content_preview TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            decision_topic TEXT NOT NULL,
            decision_result TEXT NOT NULL,
            rationale TEXT,
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        )
    ''')

    conn.commit()
    conn.close()

def add_document(
    title: str,
    file_path: str,
    doc_type: str,
    status: str,
    tags: Optional[List[str]] = None,
    summary: Optional[str] = None,
    content_preview: Optional[str] = None
) -> int:
    """添加文档记录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO documents
        (title, file_path, doc_type, status, created_date, tags, summary, content_preview)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        title,
        file_path,
        doc_type,
        status,
        datetime.now().strftime("%Y-%m-%d"),
        ",".join(tags) if tags else "",
        summary,
        content_preview
    ))

    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id

def add_decision(
    doc_id: int,
    decision_topic: str,
    decision_result: str,
    rationale: Optional[str] = None
):
    """添加决策记录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO decisions (doc_id, decision_topic, decision_result, rationale)
        VALUES (?, ?, ?, ?)
    ''', (doc_id, decision_topic, decision_result, rationale))

    conn.commit()
    conn.close()

def search_documents(query: str) -> List[Dict]:
    """搜索文档"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM documents
        WHERE title LIKE ? OR tags LIKE ? OR summary LIKE ?
    ''', (f"%{query}%", f"%{query}%", f"%{query}%"))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "title": row[1],
            "file_path": row[2],
            "doc_type": row[3],
            "status": row[4],
            "created_date": row[5],
            "tags": row[6].split(",") if row[6] else [],
            "summary": row[7]
        }
        for row in rows
    ]

def list_all_documents() -> List[Dict]:
    """列出所有文档"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM documents ORDER BY created_date DESC")
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "title": row[1],
            "file_path": row[2],
            "doc_type": row[3],
            "status": row[4],
            "created_date": row[5],
            "tags": row[6].split(",") if row[6] else [],
            "summary": row[7]
        }
        for row in rows
    ]


if __name__ == "__main__":
    # 初始化数据库
    init_db()
    print(f"数据库已创建: {DB_PATH}")

    # 添加初始文档记录
    doc_id = add_document(
        title="决策 - UI 设计风格与主题系统",
        file_path="71-decisions/决策-UI设计风格与主题系统.md",
        doc_type="decision",
        status="决策记录，已冻结",
        tags=["UI", "主题", "设计决策", "DeepSeek"],
        summary="记录 UI 原型的设计风格定位、主题系统设计、图标策略等关键决策",
        content_preview="采用 DeepSeek 简约风格作为默认主题，实现 4 种主题风格切换..."
    )
    print(f"已添加文档: ID={doc_id}")

    # 添加决策记录
    add_decision(
        doc_id=doc_id,
        decision_topic="整体风格定位",
        decision_result="采用 DeepSeek 简约风格作为默认主题",
        rationale="用户偏好极简黑白灰风格，简约风格更专业，适合论文写作场景"
    )
    add_decision(
        doc_id=doc_id,
        decision_topic="主题系统",
        decision_result="实现 4 种主题风格，通过 CSS 变量切换",
        rationale="适应不同用户偏好，实现简单，无额外依赖"
    )
    add_decision(
        doc_id=doc_id,
        decision_topic="图标策略",
        decision_result="使用 SVG 图标，完全移除 emoji",
        rationale="Emoji 显示不一致且不专业，SVG 可精确控制"
    )
    add_decision(
        doc_id=doc_id,
        decision_topic="布局结构",
        decision_result="采用 Tab 切换式布局",
        rationale="WPS TaskPane 宽度有限，Tab 切换更节省空间"
    )
    add_decision(
        doc_id=doc_id,
        decision_topic="WPS 集成",
        decision_result="Vite 构建使用相对路径 base: './'",
        rationale="WPS TaskPane 加载本地 HTML，绝对路径会 404"
    )
    print("已添加决策记录")

    # 测试搜索
    results = search_documents("主题")
    print(f"\n搜索'主题': {len(results)} 条结果")
    for r in results:
        print(f"  - {r['title']}")
