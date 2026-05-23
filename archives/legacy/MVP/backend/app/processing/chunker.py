"""文本切分策略 - 混合语义与固定大小.

切分策略：
1. 如果两个语义块合计不超过 32k → 打包一起
2. 如果超过 32k：
   - 情况1：超过但单个不超过 → 分开，不用重叠
   - 情况2：超过且单个也超过 → 平均切分到 24k，首尾重叠接近 32k
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import get_settings

settings = get_settings()


class TokenCounter(Protocol):
    """Token 计数器协议."""

    def __call__(self, text: str) -> int:
        """计算文本的 token 数量."""
        ...


def default_token_counter(text: str) -> int:
    """默认 token 计数器（粗略估计：中文*1.5 + 英文*0.75）."""
    import re

    # 中文
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    # 英文/数字/符号
    non_chinese = len(text) - chinese_chars

    return int(chinese_chars * 1.5 + non_chinese * 0.75)


@dataclass(frozen=True)
class SemanticChunk:
    """语义块.

    Attributes:
        content: 文本内容
        section: 所属章节
        metadata: 元数据
    """

    content: str
    section: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        """估算 token 数量."""
        return default_token_counter(self.content)


@dataclass(frozen=True)
class TextChunk:
    """切分后的文本块.

    Attributes:
        content: 文本内容
        section: 所属章节
        start_pos: 在原文中的起始位置
        end_pos: 在原文中的结束位置
        metadata: 元数据
    """

    content: str
    section: str = ""
    start_pos: int = 0
    end_pos: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        """估算 token 数量."""
        return default_token_counter(self.content)


def pack_chunks_if_fit(
    chunks: list[SemanticChunk],
    max_tokens: int | None = None,
) -> list[SemanticChunk]:
    """打包两个语义块（如果合计不超过阈值）.

    Args:
        chunks: 语义块列表
        max_tokens: 打包阈值（默认 32k）

    Returns:
        打包后的语义块列表
    """
    if max_tokens is None:
        max_tokens = settings.chunk_pack_threshold

    if len(chunks) < 2:
        return chunks

    result: list[SemanticChunk] = []
    i = 0

    while i < len(chunks):
        current = chunks[i]

        # 尝试与下一个合并
        if i + 1 < len(chunks):
            next_chunk = chunks[i + 1]
            combined_tokens = current.token_count + next_chunk.token_count

            if combined_tokens <= max_tokens:
                # 可以打包
                combined_content = f"{current.content}\n\n{next_chunk.content}"
                combined_section = f"{current.section} + {next_chunk.section}"
                result.append(
                    SemanticChunk(
                        content=combined_content,
                        section=combined_section,
                        metadata={
                            "packed": True,
                            "original_sections": [current.section, next_chunk.section],
                        },
                    )
                )
                i += 2
                continue

        # 不能打包，保持原样
        result.append(current)
        i += 1

    return result


def split_long_chunk(
    chunk: SemanticChunk,
    target_size: int,
    overlap_buffer: int,
) -> list[TextChunk]:
    """切分超长语义块.

    Args:
        chunk: 语义块
        target_size: 目标大小（token）
        overlap_buffer: 重叠缓冲（token）

    Returns:
        切分后的文本块列表
    """
    total_tokens = chunk.token_count

    # 计算切分数
    n_chunks = max(1, int(total_tokens / target_size))

    # 每块实际大小（多出来的平均分配）
    chunk_size = total_tokens / n_chunks

    # 计算重叠量（尽可能接近 32k）
    max_context = settings.chunk_max_context
    overlap = max(0, min(overlap_buffer, max_context - chunk_size))

    # 按字符比例切分
    content = chunk.content
    content_len = len(content)
    chars_per_chunk = int(content_len / n_chunks)
    overlap_chars = int(overlap * content_len / total_tokens)

    result: list[TextChunk] = []
    pos = 0

    for i in range(n_chunks):
        # 计算当前块的结束位置
        if i == n_chunks - 1:
            # 最后一块，取到结尾
            end = content_len
        else:
            end = min(pos + chars_per_chunk + overlap_chars, content_len)

        # 提取内容
        sub_content = content[pos:end].strip()

        result.append(
            TextChunk(
                content=sub_content,
                section=chunk.section,
                start_pos=pos,
                end_pos=end,
                metadata={
                    "chunk_index": i,
                    "total_chunks": n_chunks,
                    "is_split": True,
                },
            )
        )

        # 移动到下一块（考虑重叠）
        pos = end - overlap_chars if i < n_chunks - 1 else end

    return result


def chunk_by_semantic_units(
    chunks: list[SemanticChunk],
    token_counter: TokenCounter | None = None,
) -> list[TextChunk]:
    """按语义单元切分.

    策略：
    1. 先尝试打包（两个不超过 32k）
    2. 如果超过 32k：
       - 单个不超过 → 分开，不用重叠
       - 单个超过 → 平均切分 + 重叠

    Args:
        chunks: 语义块列表
        token_counter: Token 计数器（可选）

    Returns:
        切分后的文本块列表
    """
    if token_counter is None:
        token_counter = default_token_counter

    max_context = settings.chunk_max_context
    target_size = settings.chunk_target_size
    overlap_buffer = settings.chunk_overlap_buffer
    pack_threshold = settings.chunk_pack_threshold

    result: list[TextChunk] = []

    i = 0
    while i < len(chunks):
        current = chunks[i]
        current_tokens = current.token_count

        # 尝试与下一个合并
        if i + 1 < len(chunks):
            next_chunk = chunks[i + 1]
            combined_tokens = current_tokens + next_chunk.token_count

            if combined_tokens <= pack_threshold:
                # 情况1: 可以打包
                combined_content = f"{current.content}\n\n{next_chunk.content}"
                result.append(
                    TextChunk(
                        content=combined_content,
                        section=current.section,
                        metadata={"packed": True},
                    )
                )
                i += 2
                continue

            # 情况2: 超过打包阈值
            if current_tokens <= max_context and next_chunk.token_count <= max_context:
                # 情况2a: 单个都不超过，分开，不用重叠
                result.append(
                    TextChunk(
                        content=current.content,
                        section=current.section,
                        metadata={"split_reason": "separate_safe"},
                    )
                )
                result.append(
                    TextChunk(
                        content=next_chunk.content,
                        section=next_chunk.section,
                        metadata={"split_reason": "separate_safe"},
                    )
                )
                i += 2
                continue

            # 情况2b: 至少一个超过 max_context
            # 先处理当前块
            if current_tokens > max_context:
                result.extend(split_long_chunk(current, target_size, overlap_buffer))

                # 处理下一块
                if next_chunk.token_count > max_context:
                    result.extend(split_long_chunk(next_chunk, target_size, overlap_buffer))
                else:
                    result.append(
                        TextChunk(
                            content=next_chunk.content,
                            section=next_chunk.section,
                            metadata={"split_reason": "after_long_split"},
                        )
                    )
                i += 2
                continue

        # 情况3: 最后一个块，或者下一个合并后不安全
        if current_tokens > max_context:
            result.extend(split_long_chunk(current, target_size, overlap_buffer))
        else:
            result.append(
                TextChunk(
                    content=current.content,
                    section=current.section,
                    metadata={"split_reason": "single_safe"},
                )
            )

        i += 1

    return result


# 便捷函数
def chunk_text(
    text: str,
    section: str = "",
    target_size: int | None = None,
) -> list[TextChunk]:
    """切分单个文本.

    Args:
        text: 文本内容
        section: 所属章节
        target_size: 目标大小（可选）

    Returns:
        切分后的文本块列表
    """
    chunk = SemanticChunk(content=text, section=section)
    return chunk_by_semantic_units([chunk])
