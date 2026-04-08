"""MinerU content_list_v2.json 清洗模块.

参考 Novel_Agents RAG 工具实现。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.models.base import Chunk


# ────────────────────────────────────────────
# 噪声过滤
# ────────────────────────────────────────────

# 精确匹配
_NOISE_EXACT: frozenset[str] = frozenset({
    "Expand table",
    "Tip",
    "Note",
    "Important",
    "Warning",
    "Caution",
    "Before:",
    "After:",
    "Coming soon...",
    ".NET CLI",
    "Summarize this article for me",
    "Python",
    "Bash",
    "C#",
    "Console",
    "JSON",
    "TypeScript",
    "JavaScript",
    "Java",
    "Go",
})

# 前缀匹配
_NOISE_PREFIXES: tuple[str, ...] = (
    "Last updated on ",
    "ﾉ ",
    "L」 ",
)

# 正则匹配
_NOISE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^`\\textcircled\d*` (Note|Tip|Important|Warning)$"),
    re.compile(r"^`\\textcircled\\scriptsize \w` (Note|Tip|Important|Warning)$"),
    re.compile(r"^[\d\W]*(Note|Tip|Important|Warning|Caution)$"),
)


def _is_noise(text: str) -> bool:
    """判断文本是否为噪声."""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in _NOISE_EXACT:
        return True
    for prefix in _NOISE_PREFIXES:
        if stripped.startswith(prefix):
            return True
    for pat in _NOISE_PATTERNS:
        if pat.match(stripped):
            return True
    return False


# ────────────────────────────────────────────
# 文本清洗
# ────────────────────────────────────────────

_SPACED_ABBREVS: dict[str, str] = {
    "L L M": "LLM",
    "G N N": "GNN",
    "R L": "RL",
    "R A G": "RAG",
    "M A G": "MAG",
}


def _strip_latex_wrappers(text: str) -> str:
    """去除 LaTeX 格式命令."""
    text = re.sub(
        r"\\(?:mathrm|mathbf|mathcal|mathfrak|text|textit|textbf|texttt)"
        r"\s*\{([^}]*)\}",
        r"\1",
        text,
    )
    text = re.sub(r"\\operatorname\s*\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:left|right|displaystyle|limits|nolimits|,|;|!|\s)\b", "", text)
    text = re.sub(r"[{}]", "", text)
    return text


def clean_text(text: str) -> str:
    """应用全部文本清洗规则."""
    if not text:
        return ""
    for spaced, fixed in _SPACED_ABBREVS.items():
        text = text.replace(spaced, fixed)
    text = _strip_latex_wrappers(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ────────────────────────────────────────────
# JSON 内容提取
# ────────────────────────────────────────────

def _extract_from_content_list(content_list: list[dict]) -> str:
    """从混合内容列表提取文本."""
    parts: list[str] = []
    for item in content_list:
        match item.get("type"):
            case "text":
                parts.append(item.get("content", "").strip())
            case "equation_inline":
                raw = item.get("content", "")
                cleaned = _strip_latex_wrappers(raw)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                if cleaned:
                    parts.append(f"`{cleaned}`")
    return " ".join(parts)


def _extract_element_text(elem_type: str, content: dict) -> tuple[str, str | None]:
    """提取元素文本和图片路径.

    Returns:
        (文本内容, 图片路径)
    """
    match elem_type:
        case "paragraph":
            text = _extract_from_content_list(content.get("paragraph_content", []))
            return text, None

        case "image":
            caption_list = content.get("image_caption", [])
            caption = " ".join(
                c.get("content", "") if isinstance(c, dict) else c
                for c in caption_list
            ).strip()
            img_path = content.get("image_source", {}).get("path", "")
            if caption:
                return f"[Image: {caption}] (path: {img_path})", img_path
            return f"[Image: description pending] (path: {img_path})", img_path

        case "table":
            caption_list = content.get("table_caption", [])
            caption = " ".join(
                c.get("content", "") if isinstance(c, dict) else c
                for c in caption_list
            ).strip()
            # 简化：直接返回 HTML（后续处理）
            html = content.get("html", "")
            return f"{caption}\n{html}" if caption else html, None

        case "equation_interline":
            latex = content.get("math_content", "") or content.get("equation_content", "")
            if latex:
                return f"$$\n{latex.strip()}\n$$", None
            return "", None

        case "algorithm":
            text = _extract_from_content_list(content.get("algorithm_content", []))
            return text, None

        case "list":
            items = []
            for item in content.get("list_content", []):
                if isinstance(item, dict):
                    items.append(
                        _extract_from_content_list(item.get("item_content", [item]))
                    )
                else:
                    items.append(str(item))
            return "\n".join(f"- {it}" for it in items if it), None

        case _:
            return "", None


# ────────────────────────────────────────────
# 主清洗逻辑
# ────────────────────────────────────────────

# 跳过的噪声类型
SKIP_TYPES = frozenset({
    "page_header",
    "page_footnote",
    "page_footnote_text",
    "page_aside_text",
    "page_number",
})


def clean_paper(paper_dir: Path, paper_id: str | None = None) -> list[Chunk]:
    """清洗单篇论文的 MinerU JSON.

    Args:
        paper_dir: MinerU 提取目录
        paper_id: 论文标识符

    Returns:
        清洗后的 Chunk 列表
    """
    if paper_id is None:
        paper_id = paper_dir.name.split(".pdf")[0].replace("《", "").replace("》", "")

    json_path = paper_dir / "content_list_v2.json"
    if not json_path.exists():
        raise FileNotFoundError(f"content_list_v2.json not found in {paper_dir}")

    data: list[list[dict]] = json.loads(json_path.read_text(encoding="utf-8"))

    chunks: list[Chunk] = []
    sections: list[str] = []
    counter = 0

    for page_idx, page_elements in enumerate(data):
        for element in page_elements:
            elem_type = element.get("type", "")

            # 跳过噪声类型
            if elem_type in SKIP_TYPES:
                continue

            # title → 更新 section 层级
            if elem_type == "title":
                title_content = element.get("content", {}).get("title_content", [])
                title_text = _extract_from_content_list(title_content)
                title_text = clean_text(title_text)
                if not title_text:
                    continue
                level = element.get("content", {}).get("level", 1)
                sections = sections[: level - 1] + [title_text]
                continue

            # 提取内容
            text, image_path = _extract_element_text(elem_type, element.get("content", {}))
            text = clean_text(text)
            if not text:
                continue

            # 过滤 UI 噪声
            if _is_noise(text):
                continue

            chunks.append(
                Chunk(
                    id=f"{paper_id}_p{page_idx}_{counter:03d}",
                    paper=paper_id,
                    chunk_type=elem_type,
                    content=text,
                    section=" > ".join(sections),
                    page=page_idx,
                    image_path=image_path,
                    metadata={"paper_dir": str(paper_dir)},
                )
            )
            counter += 1

    return chunks
