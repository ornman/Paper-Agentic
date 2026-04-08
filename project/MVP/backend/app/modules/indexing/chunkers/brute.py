# brute 切块器
# 目标：
# 1. 把清洗后的正文块压平成 token 流
# 2. 按 500~1000 token 窗口切块
# 3. 保留固定重叠，避免语义在边界被硬切断

from __future__ import annotations

from typing import Iterable

from app.modules.ingestion.dto import CleanedBlock, CleanedDocument
from app.modules.indexing.dto import BruteIndexBuildResult, IndexedChunk

# 这里取一个落在要求区间内部的固定值：
# - 800 token 主窗口
# - 100 token 重叠
# 这样既满足“500~1000 token 切块”，也足够简单稳定，适合当前最小实现。
DEFAULT_BRUTE_CHUNK_SIZE = 800
DEFAULT_BRUTE_OVERLAP = 100
_MIN_ALLOWED_CHUNK_SIZE = 500
_MAX_ALLOWED_CHUNK_SIZE = 1000


def _contains_cjk_character(text: str) -> bool:
    """判断文本里是否包含中日韩统一表意文字。

    这里单独抽成函数，而不是继续靠正则大吞块，原因是：
    1. 当前故障不是“不会分词”，而是“连续中文被 \\S+ 整段吞掉”。
    2. brute 切块阶段只需要稳定窗口，不需要语言学级别分词。
    3. 对连续 CJK 文本按字符切分，能最小成本保证窗口长度稳定。
    """
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def tokenize_text(text: str) -> list[str]:
    """把文本切成稳定 token 序列。

    这里不引入重量级 tokenizer，原因是 Task 5 只需要“稳定、可预测”的切块。
    实现策略：
    1. 如果文本包含空白，优先按空白切分，兼容测试里人工构造的 token 流。
    2. 如果文本不含空白且包含连续中文，退化为逐字符切分。
       这样可以直接修复“1600 个中文字符被误当成 1 个 token”的根因。
    3. 其余无空白文本再整体保留，避免把普通 ASCII 标识符切得过碎。
    """
    stripped_text = text.strip()
    if not stripped_text:
        return []

    if any(character.isspace() for character in stripped_text):
        return [token for token in stripped_text.split() if token]

    if _contains_cjk_character(stripped_text):
        return [character for character in stripped_text if not character.isspace()]

    return [stripped_text]


def flatten_blocks(blocks: Iterable[CleanedBlock]) -> list[dict]:
    """把正文块压平成 token 流，并保留来源定位信息。"""
    flattened_tokens: list[dict] = []
    for block in blocks:
        for token in tokenize_text(block.text):
            flattened_tokens.append(
                {
                    "token": token,
                    "page": block.page,
                    "block_id": block.block_id,
                }
            )
    return flattened_tokens


def _should_render_token_window_without_spaces(token_window: list[dict]) -> bool:
    """判断当前窗口是否应该按连续正文回拼，而不是用空格连接。

    修复原因：
    1. 连续中文在 tokenize_text() 里会按字符切开，这是为了稳定窗口长度。
    2. 但如果在回写 chunk.text 时再用空格 join，就会把原始正文污染成“人 工 智 能”。
    3. 这种污染会同时影响展示文本和 BM25 文本。

    这里采用最小保守规则：
    - 只有当窗口内 token 全是单字符，且至少包含一个中文字符时，
      才认定它来自“连续无空格中文正文”，回拼时不插空格。
    - 这样不会影响当前英文/ID 风格 token 的空格连接行为。
    """
    tokens = [item["token"] for item in token_window]
    if not tokens:
        return False
    return all(len(token) == 1 for token in tokens) and any(
        _contains_cjk_character(token) for token in tokens
    )


def _render_chunk_text(token_window: list[dict]) -> str:
    """把 token 窗口恢复成最终 chunk 文本。"""
    tokens = [item["token"] for item in token_window]
    if _should_render_token_window_without_spaces(token_window):
        return "".join(tokens)
    return " ".join(tokens)



def build_chunk_from_token_window(
    *,
    document_id: str,
    chunk_id: str,
    token_window: list[dict],
    node_kind: str,
    searchable: bool,
    parent_chunk_id: str | None = None,
) -> IndexedChunk:
    """根据 token 窗口构造统一块对象。"""
    pages = [item["page"] for item in token_window]
    source_block_ids = list(dict.fromkeys(item["block_id"] for item in token_window))
    return IndexedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=_render_chunk_text(token_window),
        page_start=min(pages) if pages else 0,
        page_end=max(pages) if pages else 0,
        source_block_ids=source_block_ids,
        node_kind=node_kind,  # type: ignore[arg-type]
        searchable=searchable,
        parent_chunk_id=parent_chunk_id,
    )


def iter_token_windows(
    flattened_tokens: list[dict],
    *,
    chunk_size: int,
    overlap: int,
) -> list[list[dict]]:
    """按窗口大小和重叠切分 token 流。"""
    if chunk_size < _MIN_ALLOWED_CHUNK_SIZE or chunk_size > _MAX_ALLOWED_CHUNK_SIZE:
        raise ValueError(f"chunk_size 必须位于 {_MIN_ALLOWED_CHUNK_SIZE}~{_MAX_ALLOWED_CHUNK_SIZE} 之间")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须大于等于 0 且小于 chunk_size")

    if not flattened_tokens:
        return []

    windows: list[list[dict]] = []
    step = chunk_size - overlap
    start = 0

    while start < len(flattened_tokens):
        end = min(start + chunk_size, len(flattened_tokens))
        token_window = flattened_tokens[start:end]
        if token_window:
            windows.append(token_window)
        if end >= len(flattened_tokens):
            break
        start += step

    # 如果最后一个尾块过短，就把它改成“从文档尾部反推 chunk_size 的回收窗口”。
    # 这样做的本质是：
    # 1. 不再单独吐出一个 <500 token 的残块
    # 2. 保持总块数基本不变，只最小修正最后一个窗口
    # 3. 不影响前面窗口的稳定切法，避免把逻辑扩散到整个分块流程
    if len(windows) >= 2 and len(windows[-1]) < _MIN_ALLOWED_CHUNK_SIZE:
        recycled_start = max(len(flattened_tokens) - chunk_size, 0)
        recycled_window = flattened_tokens[recycled_start:]
        if len(recycled_window) >= _MIN_ALLOWED_CHUNK_SIZE:
            windows[-1] = recycled_window

    return windows


def build_brute_index(
    cleaned_document: CleanedDocument,
    *,
    chunk_size: int = DEFAULT_BRUTE_CHUNK_SIZE,
    overlap: int = DEFAULT_BRUTE_OVERLAP,
) -> BruteIndexBuildResult:
    """构建 brute 模式索引块。"""
    flattened_tokens = flatten_blocks(cleaned_document.blocks)
    token_windows = iter_token_windows(flattened_tokens, chunk_size=chunk_size, overlap=overlap)

    chunks = [
        build_chunk_from_token_window(
            document_id=cleaned_document.document_id,
            chunk_id=f"{cleaned_document.document_id}::brute::{index:04d}",
            token_window=token_window,
            node_kind="brute",
            searchable=True,
        )
        for index, token_window in enumerate(token_windows)
    ]

    return BruteIndexBuildResult(chunks=chunks)
