"""PDF 解析结果清洗器（Markdown + JSON 双格式）"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SKIP_TYPES = frozenset({
    "page_header", "page_footnote", "page_footnote_text",
    "page_aside_text", "page_number",
})

_NOISE_EXACT = frozenset({
    "Expand table", "Tip", "Bash", "Note", "Warning",
    "Caution", "Important", "Custom", "Details",
})

_NOISE_PREFIXES = ("Last updated on ",)

_NOISE_PATTERNS = (
    re.compile(r"\\textcircled\{[^}]*\}"),
    re.compile(r"^\s*\d+\.\s+(Tip|Note|Warning)\s*$", re.MULTILINE),
)

_SPACED_ABBREVS = {
    "L L M": "LLM", "N L P": "NLP", "G P U": "GPU",
    "T P U": "TPU", "C P U": "CPU",
}

_LATEX_WRAPPERS = (
    (re.compile(r"\\mathrm\{([^}]*)\}"), r"\1"),
    (re.compile(r"\\mathbf\{([^}]*)\}"), r"\1"),
    (re.compile(r"\\text\{([^}]*)\}"), r"\1"),
    (re.compile(r"\\boldsymbol\{([^}]*)\}"), r"\1"),
    (re.compile(r"\{([^}]*)\}"), r"\1"),
)


@dataclass
class Chunk:
    chunk_id: str
    content: str
    page: int
    chunk_type: str = "paragraph"
    section_title: str = ""
    file_hash: str = ""
    source_path: str = ""
    has_image: str = "false"


def clean_json_layout(pages: list[dict], paper_id: str) -> list[Chunk]:
    """从 MinerU JSON layout 解析并清洗"""
    chunks: list[Chunk] = []
    section_stack: list[str] = []

    for page_data in pages:
        page_idx = page_data.get("page", 0)
        blocks = page_data.get("blocks", [])

        for block in blocks:
            block_type = block.get("type", "")

            if block_type in _SKIP_TYPES:
                continue

            # 章节标题追踪
            if block_type == "title":
                level = block.get("level", 1)
                title_text = _extract_text(block)
                section_stack = section_stack[: level - 1] + [title_text]
                continue

            text = _extract_text(block)
            text = _clean_text(text)
            if not text:
                continue

            chunk_type = _map_type(block_type)
            has_image = "true" if block.get("type") in ("image", "table") else "false"

            chunks.append(Chunk(
                chunk_id=f"{paper_id}_p{page_idx}_{len(chunks):03d}",
                content=text,
                page=page_idx,
                chunk_type=chunk_type,
                section_title=" > ".join(section_stack) if section_stack else "",
                has_image=has_image,
            ))

    return chunks


def clean_markdown(md_content: str, paper_id: str) -> list[Chunk]:
    """从 Markdown 文本提取语义块"""
    chunks: list[Chunk] = []
    section_stack: list[str] = []

    lines = md_content.split("\n")
    current_content: list[str] = []
    current_page = 0

    def flush():
        if not current_content:
            return
        text = "\n".join(current_content).strip()
        text = _clean_text(text)
        if text:
            chunks.append(Chunk(
                chunk_id=f"{paper_id}_md_{len(chunks):03d}",
                content=text,
                page=current_page,
                chunk_type="paragraph",
                section_title=" > ".join(section_stack) if section_stack else "",
            ))
        current_content.clear()

    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            section_stack = section_stack[: level - 1] + [title]
            continue

        # 页码标记
        page_marker = re.match(r"<!--\s*page\s*(\d+)\s*-->", line)
        if page_marker:
            current_page = int(page_marker.group(1))
            continue

        if line.strip():
            current_content.append(line)
        elif current_content:
            flush()

    flush()
    return chunks


def _extract_text(block: dict) -> str:
    block_type = block.get("type", "")

    match block_type:
        case "image":
            return block.get("text", "") or f"[Image: {block.get('img_idx', '')}]"
        case "table":
            return block.get("text", "") or block.get("html", "")
        case "equation_interline":
            return block.get("latex", "") or block.get("text", "")
        case _:
            return block.get("text", "")


def _map_type(block_type: str) -> str:
    mapping = {
        "text": "paragraph",
        "paragraph": "paragraph",
        "image": "image",
        "table": "table",
        "equation_interline": "equation",
        "equation_inline": "equation",
        "list": "list",
        "algorithm": "algorithm",
    }
    return mapping.get(block_type, "paragraph")


def _clean_text(text: str) -> str:
    if not text:
        return ""

    # LaTeX 包装器剥离
    for pattern, repl in _LATEX_WRAPPERS:
        text = pattern.sub(repl, text)

    # 缩写修复
    for abbr, fix in _SPACED_ABBREVS.items():
        text = text.replace(abbr, fix)

    # 噪音过滤
    text = text.strip()
    if text in _NOISE_EXACT:
        return ""
    for prefix in _NOISE_PREFIXES:
        if text.startswith(prefix):
            return ""
    for pattern in _NOISE_PATTERNS:
        text = pattern.sub("", text)

    # 清理多余空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
