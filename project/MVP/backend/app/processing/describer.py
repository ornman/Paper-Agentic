"""VLM 图片描述服务.

为图片类 Chunk 生成结构化文本描述，支持并发请求和缓存。
使用抽象 VLMClient 接口，可替换实现。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.clients.vlm_client import VLMClient
from app.clients.kimi_client import KimiVLMClient
from app.core.config import get_settings
from app.models.base import Chunk

settings = get_settings()

CACHE_FILENAME = "image_descriptions.json"
CONCURRENCY = settings.kimi_vlm_concurrency


def _load_cache(paper_dir: Path) -> dict[str, str]:
    """加载图片描述缓存."""
    cache_path = paper_dir / CACHE_FILENAME
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(paper_dir: Path, cache: dict[str, str]) -> None:
    """保存图片描述缓存."""
    cache_path = paper_dir / CACHE_FILENAME
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def describe_chunks_async(
    paper_dir: Path,
    chunks: list[Chunk],
    vlm_client: VLMClient | None = None,
) -> list[Chunk]:
    """异步为图片类 Chunk 生成 VLM 描述.

    Args:
        paper_dir: 论文目录（用于缓存）
        chunks: Chunk 列表
        vlm_client: VLM 客户端（默认使用 KimiVLMClient）

    Returns:
        更新后的 Chunk 列表（content 包含图片描述）
    """
    if vlm_client is None:
        vlm_client = KimiVLMClient()

    cache = _load_cache(paper_dir)

    # 收集需要描述的图片
    to_describe: list[tuple[int, Chunk]] = []
    for i, chunk in enumerate(chunks):
        if not chunk.image_path:
            continue
        abs_path = paper_dir / chunk.image_path
        if not abs_path.exists():
            continue
        rel_path = str(chunk.image_path)
        if rel_path not in cache:
            to_describe.append((i, chunk))

    # 并发调用 VLM
    if to_describe:
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def _describe_one(index: int, chunk: Chunk) -> tuple[int, str, str]:
            abs_path = paper_dir / chunk.image_path
            try:
                description = await vlm_client.describe_image(abs_path)
                return index, str(chunk.image_path), description
            except Exception as e:
                print(f"[WARN] VLM failed for {chunk.image_path}: {e}")
                return index, str(chunk.image_path), "description unavailable"

        async def _run_batch():
            tasks = [
                _describe_one(i, chunk)
                for i, chunk in to_describe
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [
                r for r in results
                if not isinstance(r, Exception)
            ]

        print(f"    VLM: {len(to_describe)} images to describe ({CONCURRENCY} concurrent)...")

        results = await _run_batch()
        for index, rel_path, description in results:
            cache[rel_path] = description

        _save_cache(paper_dir, cache)
        print(f"    VLM: done, cache updated ({len(cache)} total)")

    # 构建结果
    result: list[Chunk] = []
    for chunk in chunks:
        if not chunk.image_path:
            result.append(chunk)
            continue

        abs_path = paper_dir / chunk.image_path
        if not abs_path.exists():
            result.append(chunk)
            continue

        rel_path = str(chunk.image_path)
        description = cache.get(rel_path, "description unavailable")

        result.append(
            Chunk(
                id=chunk.id,
                paper=chunk.paper,
                chunk_type=chunk.chunk_type,
                content=f"[Image]\nDescription: {description}\nOriginal: {chunk.content}",
                section=chunk.section,
                page=chunk.page,
                image_path=chunk.image_path,
                metadata=chunk.metadata,
            )
        )

    return result


def describe_chunks(
    paper_dir: Path,
    chunks: list[Chunk],
    vlm_client: VLMClient | None = None,
) -> list[Chunk]:
    """同步为图片类 Chunk 生成 VLM 描述.

    Args:
        paper_dir: 论文目录
        chunks: Chunk 列表
        vlm_client: VLM 客户端（默认使用 KimiVLMClient）

    Returns:
        更新后的 Chunk 列表
    """
    return asyncio.run(describe_chunks_async(paper_dir, chunks, vlm_client))
