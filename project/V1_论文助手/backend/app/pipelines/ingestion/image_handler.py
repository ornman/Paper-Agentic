"""图片处理器：提取图片 → VLM 描述 → 附加到 Markdown"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from app.clients.vlm_client import VLMClient
from app.pipelines.ingestion.cleaner import Chunk

logger = logging.getLogger("paper-assistant")

_CONCURRENCY = 10


class ImageHandler:
    def __init__(self, vlm_client: VLMClient):
        self._vlm = vlm_client
        self._semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def describe_images_in_chunks(
        self,
        chunks: list[Chunk],
        paper_dir: str,
    ) -> list[Chunk]:
        """为含有图片引用的 chunk 生成 VLM 描述"""
        images_dir = os.path.join(paper_dir, "images")
        cache_path = os.path.join(paper_dir, "image_descriptions.json")
        cache = self._load_cache(cache_path)

        tasks = []
        for chunk in chunks:
            if chunk.has_image != "true":
                continue
            img_ref = _extract_image_ref(chunk.content)
            if not img_ref:
                continue
            img_path = os.path.join(images_dir, img_ref)
            if not os.path.exists(img_path):
                continue
            if img_ref in cache:
                chunk.content = _append_description(chunk.content, cache[img_ref])
                continue
            tasks.append((chunk, img_ref, img_path))

        if not tasks:
            return chunks

        async def _describe_one(chunk: Chunk, ref: str, path: str):
            async with self._semaphore:
                desc = await self._vlm.describe_image(path)
                cache[ref] = desc
                chunk.content = _append_description(chunk.content, desc)

        await asyncio.gather(
            *[_describe_one(c, r, p) for c, r, p in tasks],
            return_exceptions=True,
        )

        self._save_cache(cache_path, cache)
        return chunks

    @staticmethod
    def _load_cache(path: str) -> dict[str, str]:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    @staticmethod
    def _save_cache(path: str, cache: dict[str, str]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)


def _extract_image_ref(content: str) -> str | None:
    """从内容中提取图片路径引用"""
    import re
    m = re.search(r"!\[.*?\]\((.*?)\)", content)
    if m:
        return m.group(1)
    m = re.search(r"\[Image[^\]]*\]\((.*?)\)", content)
    if m:
        return m.group(1)
    m = re.search(r"images/[\w.\-]+", content)
    if m:
        return m.group(0)
    return None


def _append_description(content: str, description: str) -> str:
    return f"{content}\n\n[Image Description: {description}]"
