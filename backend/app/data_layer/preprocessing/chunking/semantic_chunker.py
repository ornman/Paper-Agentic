"""语义切分器

基于嵌入向量的语义边界检测，生成带锚点的 chunk。
增强特性：heading-aware 边界、表格/公式保护、超长块重切、MinerU metadata 锚点填充。
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field

# 切分约束
MIN_CHUNK_TOKENS = 128
MAX_CHUNK_TOKENS = 512
OVERLAP_TOKENS = int(MAX_CHUNK_TOKENS * 0.10)  # 超长块重切时的 overlap（10%）
SIMILARITY_DROP_THRESHOLD = 0.3  # 相似度下降 30% = 语义边界
EMBEDDING_WINDOW_SIZE = 3  # 滑动窗口大小


@dataclass
class Anchor:
    """原文锚点"""
    anchor_id: str
    source_file_path: str = ""
    doc_type: str = "pdf"
    page: int = 0
    block_id: str = ""
    block_type: str = "paragraph"  # paragraph / heading / table / formula / figure
    heading_path: list[str] = field(default_factory=list)
    paragraph_index: int = 0
    char_start: int = 0
    char_end: int = 0
    bbox: list[float] = field(default_factory=list)
    parent_anchor_id: str = ""
    source_text_hash: str = ""


@dataclass
class Chunk:
    """切片结果"""
    chunk_id: str
    content: str
    anchors: list[Anchor] = field(default_factory=list)
    token_count: int = 0
    section_title: str = ""
    section_level: int = 0
    chunk_type: str = "paragraph"  # paragraph / heading / table / formula / figure
    has_image: bool = False
    parent_chunk_id: str = ""  # 超长块重切时，子块指向原父块


def semantic_chunk(
    markdown: str,
    source_file_path: str = "",
    embedding_func=None,
    mineru_metadata: dict | None = None,
) -> list[Chunk]:
    """语义切分

    Args:
        markdown: 清洗后的 markdown
        source_file_path: 源文件路径（用于锚点）
        embedding_func: 嵌入函数（可选，用于基于向量的语义切分）
        mineru_metadata: MinerU 解析元数据（可选，用于填充 anchor 的 page/bbox/block_type）

    Returns:
        Chunk 列表
    """
    if not markdown.strip():
        return []

    # 1. 按句子分割（带 heading/table/formula 保护）
    sentences = _split_sentences(markdown)

    # 2. 如果有嵌入函数，使用向量相似度检测语义边界
    if embedding_func:
        boundaries = _detect_boundaries_by_embedding(sentences, embedding_func)
    else:
        # 降级：基于规则的切分（含 heading-aware）
        boundaries = _detect_boundaries_by_rules(sentences)

    # 3. 根据边界切分
    chunks = _split_by_boundaries(sentences, boundaries, source_file_path)

    # 4. 超长块重切
    chunks = _rechunk_oversized(chunks, source_file_path)

    # 5. 用 MinerU metadata 增强 anchor
    if mineru_metadata:
        _enrich_anchors_from_metadata(chunks, mineru_metadata, source_file_path)

    # 6. 图片父子块关系
    _mark_figure_blocks(chunks, source_file_path)

    return chunks


def _split_sentences(text: str) -> list[dict]:
    """按句子分割文本，保护表格/公式/脚注

    Returns:
        [{"text": str, "start": int, "end": int, "is_heading": bool, "heading_level": int}]
    """
    sentences = []
    current_start = 0

    # 先按行分割，识别 heading、表格、公式块
    lines = text.split("\n")
    offset = 0

    for line in lines:
        line_end = offset + len(line) + 1  # +1 for \n

        # 检测 heading
        heading_match = re.match(r"^(#{1,6})\s+", line)
        if heading_match:
            # 先保存之前积累的普通文本
            if offset > current_start:
                _split_normal_text(text[current_start:offset], current_start, sentences)
            # heading 作为一个整块
            sentences.append({
                "text": line,
                "start": offset,
                "end": line_end - 1,
                "is_heading": True,
                "heading_level": len(heading_match.group(1)),
            })
            current_start = line_end
            offset = line_end
            continue

        # 检测表格行（|...|）
        if re.match(r"^\s*\|", line):
            # 表格行不作为切分边界，但需要记录
            offset = line_end
            continue

        # 检测公式块（$$...$$）
        if line.strip().startswith("$$"):
            offset = line_end
            continue

        offset = line_end

    # 处理剩余文本
    if current_start < len(text):
        _split_normal_text(text[current_start:], current_start, sentences)

    return sentences


def _split_normal_text(text: str, base_offset: int, sentences: list[dict]):
    """将普通文本按句号等分割（保护 markdown 图片语法和文件路径中的点号）"""
    # ! 后跟 [ 是 markdown 图片语法，不分割
    # . 前后都是字母数字是文件扩展名（如 file.pdf），不分割
    # 中文句号直接分割
    # 英文 .!?; 分割条件：后面跟空白或行尾，且 ! 后不是 [（图片语法）
    pattern = re.compile(r"([。！？；]|[.!?;](?=\s+|$)(?!\[))")
    current_start = 0

    for match in pattern.finditer(text):
        end = match.end()
        sentence_text = text[current_start:end].strip()
        if sentence_text:
            sentences.append({
                "text": sentence_text,
                "start": base_offset + current_start,
                "end": base_offset + end,
                "is_heading": False,
                "heading_level": 0,
            })
        current_start = end

    remaining = text[current_start:].strip()
    if remaining:
        sentences.append({
            "text": remaining,
            "start": base_offset + current_start,
            "end": base_offset + len(text),
            "is_heading": False,
            "heading_level": 0,
        })


def _detect_boundaries_by_embedding(
    sentences: list[dict],
    embedding_func,
) -> list[int]:
    """基于嵌入向量检测语义边界

    Args:
        sentences: 句子列表
        embedding_func: 嵌入函数

    Returns:
        边界索引列表
    """
    if len(sentences) < 2:
        return []

    # 计算每个句子的嵌入
    texts = [s["text"] for s in sentences]
    embeddings = embedding_func(texts)

    if not embeddings or len(embeddings) != len(sentences):
        return []

    # 滑动窗口计算相似度
    boundaries = []
    window_similarities = []

    for i in range(len(embeddings) - 1):
        similarity = _cosine_similarity(embeddings[i], embeddings[i + 1])
        window_similarities.append(similarity)

    # 计算平均相似度（滑动窗口）
    for i in range(len(window_similarities)):
        start_idx = max(0, i - EMBEDDING_WINDOW_SIZE + 1)
        window = window_similarities[start_idx:i + 1]
        avg_similarity = sum(window) / len(window)

        # 检测显著下降
        if i > 0:
            prev_avg = sum(window_similarities[max(0, i - EMBEDDING_WINDOW_SIZE):i]) / min(i, EMBEDDING_WINDOW_SIZE)
            drop = (prev_avg - avg_similarity) / prev_avg if prev_avg > 0 else 0

            if drop > SIMILARITY_DROP_THRESHOLD:
                # 在附近找自然句子结束位置
                boundary_idx = _find_natural_boundary(sentences, i)
                if boundary_idx not in boundaries:
                    boundaries.append(boundary_idx)

    # heading 强制切分
    for i, s in enumerate(sentences):
        if s.get("is_heading") and i not in boundaries:
            boundaries.append(i)

    return sorted(boundaries)


def _detect_boundaries_by_rules(sentences: list[dict]) -> list[int]:
    """基于规则检测语义边界（降级方案），含 heading-aware

    Args:
        sentences: 句子列表

    Returns:
        边界索引列表
    """
    boundaries = []
    current_tokens = 0

    for i, sentence in enumerate(sentences):
        # heading 强制切分
        if sentence.get("is_heading"):
            if i > 0:
                boundaries.append(i - 1)
            current_tokens = 0
            continue

        sentence_tokens = estimate_tokens(sentence["text"])
        current_tokens += sentence_tokens

        # 超过最大 token 限制，切分
        if current_tokens >= MAX_CHUNK_TOKENS:
            boundaries.append(i)
            current_tokens = sentence_tokens

    return boundaries


def _find_natural_boundary(sentences: list[dict], near_idx: int) -> int:
    """在附近找自然句子结束位置

    Args:
        sentences: 句子列表
        near_idx: 附近索引

    Returns:
        自然边界索引
    """
    # 向前找句子结束位置
    for i in range(near_idx, max(0, near_idx - 3), -1):
        text = sentences[i]["text"]
        if text.endswith(("。", "！", "？", ".", "!", "?")):
            return i

    return near_idx


def _split_by_boundaries(
    sentences: list[dict],
    boundaries: list[int],
    source_file_path: str,
) -> list[Chunk]:
    """根据边界切分句子为 chunk

    Args:
        sentences: 句子列表
        边界索引列表
        source_file_path: 源文件路径

    Returns:
        Chunk 列表
    """
    chunks = []
    current_start = 0

    for boundary in boundaries:
        # 切分当前段
        chunk_sentences = sentences[current_start:boundary + 1]
        if chunk_sentences:
            chunk = _create_chunk(chunk_sentences, len(chunks), source_file_path)
            chunks.append(chunk)
        current_start = boundary + 1

    # 处理最后一段
    if current_start < len(sentences):
        chunk_sentences = sentences[current_start:]
        chunk = _create_chunk(chunk_sentences, len(chunks), source_file_path)
        chunks.append(chunk)

    return chunks


def _create_chunk(
    sentences: list[dict],
    chunk_index: int,
    source_file_path: str,
) -> Chunk:
    """创建 chunk

    Args:
        sentences: 句子列表
        chunk_index: chunk 索引
        source_file_path: 源文件路径

    Returns:
        Chunk
    """
    content = "\n".join(s["text"] for s in sentences)
    char_start = sentences[0]["start"]
    char_end = sentences[-1]["end"]

    # 检测是否为 heading chunk
    is_heading = any(s.get("is_heading") for s in sentences)
    heading_level = 0
    section_title = ""
    block_type = "paragraph"
    if is_heading:
        for s in sentences:
            if s.get("is_heading"):
                heading_level = s.get("heading_level", 1)
                section_title = s["text"].lstrip("#").strip()
                block_type = "heading"
                break

    # 创建锚点
    anchor = Anchor(
        anchor_id=f"anchor_{chunk_index:04d}",
        source_file_path=source_file_path,
        char_start=char_start,
        char_end=char_end,
        paragraph_index=chunk_index,
        block_type=block_type,
        source_text_hash=hashlib.sha256(content.encode()).hexdigest()[:16],
    )

    return Chunk(
        chunk_id=f"chunk_{chunk_index:04d}",
        content=content,
        anchors=[anchor],
        token_count=estimate_tokens(content),
        section_title=section_title,
        section_level=heading_level,
        chunk_type=block_type,
    )


def _rechunk_oversized(chunks: list[Chunk], source_file_path: str) -> list[Chunk]:
    """超长块重切：超过 MAX_CHUNK_TOKENS 的 chunk 按 MAX_CHUNK_TOKENS 重切，带 overlap"""
    result = []
    for chunk in chunks:
        if chunk.token_count <= MAX_CHUNK_TOKENS:
            result.append(chunk)
            continue

        # 超长块需要重切
        text = chunk.content
        parent_anchor_id = chunk.anchors[0].anchor_id if chunk.anchors else ""
        sub_chunks = _split_oversized_text(
            text, len(result), source_file_path, parent_anchor_id, chunk.chunk_id,
        )
        result.extend(sub_chunks)

    return result


def _split_oversized_text(
    text: str,
    base_index: int,
    source_file_path: str,
    parent_anchor_id: str,
    parent_chunk_id: str = "",
) -> list[Chunk]:
    """将超长文本切分为多个 chunk，带 overlap"""
    # 按 MAX_CHUNK_TOKENS 估算字符数（粗略：1 token ≈ 1.5 中文字符 或 4 英文字符）
    chars_per_token = 1.5  # 偏中文
    max_chars = int(MAX_CHUNK_TOKENS * chars_per_token)
    overlap_chars = int(OVERLAP_TOKENS * chars_per_token)

    chunks = []
    pos = 0

    while pos < len(text):
        end = min(pos + max_chars, len(text))

        # 尝试在自然边界切分
        if end < len(text):
            # 向前找句号
            for i in range(end, max(pos + max_chars // 2, end - 200), -1):
                if i < len(text) and text[i] in "。！？.!?;":
                    end = i + 1
                    break

        chunk_text = text[pos:end].strip()
        if not chunk_text:
            pos = end
            continue

        idx = base_index + len(chunks)
        anchor = Anchor(
            anchor_id=f"anchor_{idx:04d}",
            source_file_path=source_file_path,
            char_start=pos,
            char_end=end,
            paragraph_index=idx,
            parent_anchor_id=parent_anchor_id,
            source_text_hash=hashlib.sha256(chunk_text.encode()).hexdigest()[:16],
        )

        chunks.append(Chunk(
            chunk_id=f"chunk_{idx:04d}",
            content=chunk_text,
            anchors=[anchor],
            token_count=estimate_tokens(chunk_text),
            chunk_type="paragraph",
            parent_chunk_id=parent_chunk_id,
        ))

        # 下一段从 overlap 位置开始
        pos = end - overlap_chars if end < len(text) else end

    return chunks


def _enrich_anchors_from_metadata(
    chunks: list[Chunk],
    mineru_metadata: dict,
    source_file_path: str,
):
    """用 MinerU metadata 增强 anchor 的 page/bbox/block_id/block_type"""
    content_list = mineru_metadata.get("content_list", [])
    if not content_list:
        return

    # 构建 content_list 的字符偏移映射
    offset = 0
    block_map = []  # [(start, end, block_info)]
    for block in content_list:
        block_text = block.get("text", "")
        if not block_text:
            # 图片/表格等非文本块
            block_map.append({
                "start": offset,
                "end": offset,
                "page_idx": block.get("page_idx", 0),
                "bbox": block.get("bbox", []),
                "type": block.get("type", ""),
                "block_id": block.get("index", ""),
            })
            continue

        block_map.append({
            "start": offset,
            "end": offset + len(block_text),
            "page_idx": block.get("page_idx", 0),
            "bbox": block.get("bbox", []),
            "type": block.get("type", "text"),
            "block_id": block.get("index", ""),
        })
        offset += len(block_text) + 1  # +1 for newline separator

    # 为每个 chunk 的 anchor 匹配 metadata
    for chunk in chunks:
        for anchor in chunk.anchors:
            # 找到 anchor.char_start 对应的 block
            for block_info in block_map:
                if block_info["start"] <= anchor.char_start < block_info["end"]:
                    anchor.page = block_info["page_idx"] + 1  # 1-indexed
                    anchor.bbox = block_info["bbox"]
                    anchor.block_id = str(block_info["block_id"])
                    block_type = block_info.get("type", "")
                    if block_type:
                        anchor.block_type = _map_block_type(block_type)
                    break

            # 提取 heading_path
            if not anchor.heading_path:
                anchor.heading_path = _extract_heading_path(chunks, chunk)


def _map_block_type(mineru_type: str) -> str:
    """将 MinerU block type 映射到 Anchor block_type"""
    mapping = {
        "text": "paragraph",
        "title": "heading",
        "heading": "heading",
        "table": "table",
        "equation": "formula",
        "figure": "figure",
        "image": "figure",
        "reference": "paragraph",
        "caption": "paragraph",
        "footnote": "paragraph",
    }
    return mapping.get(mineru_type, "paragraph")


def _extract_heading_path(all_chunks: list[Chunk], target_chunk: Chunk) -> list[str]:
    """提取从文档开头到目标 chunk 的 heading 路径"""
    path = []
    for chunk in all_chunks:
        if chunk is target_chunk:
            break
        if chunk.section_title and chunk.section_level > 0:
            # 维护 heading 栈：移除同级或更低级别的 heading
            while path and len(path) >= chunk.section_level:
                path.pop()
            path.append(chunk.section_title)

    return path


def _mark_figure_blocks(chunks: list[Chunk], source_file_path: str):
    """标记包含图片引用的 chunk，建立父子块关系"""
    img_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    for i, chunk in enumerate(chunks):
        matches = list(img_pattern.finditer(chunk.content))
        if not matches:
            continue

        chunk.has_image = True
        chunk.chunk_type = "figure"

        # 为图片引用创建子 anchor
        for match in matches:
            img_alt = match.group(1)
            img_path = match.group(2)
            child_anchor = Anchor(
                anchor_id=f"anchor_{i:04d}_img_{match.start()}",
                source_file_path=source_file_path,
                char_start=chunk.anchors[0].char_start + match.start() if chunk.anchors else 0,
                char_end=chunk.anchors[0].char_start + match.end() if chunk.anchors else 0,
                block_type="figure",
                parent_anchor_id=chunk.anchors[0].anchor_id if chunk.anchors else "",
                source_text_hash=hashlib.sha256(img_path.encode()).hexdigest()[:16],
            )
            chunk.anchors.append(child_anchor)


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """计算余弦相似度"""
    import math

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def estimate_tokens(text: str) -> int:
    """估算 token 数量"""
    count = 0.0
    for ch in text:
        count += 1.5 if "一" <= ch <= "鿿" else 0.75
    return int(count)
