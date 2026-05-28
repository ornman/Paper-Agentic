"""语义切分模块

基于嵌入向量的语义边界检测，生成带锚点的 chunk。
"""

from .semantic_chunker import (
    Anchor,
    Chunk,
    semantic_chunk,
    estimate_tokens,
)

__all__ = [
    "semantic_chunk",
    "Chunk",
    "Anchor",
    "estimate_tokens",
]
