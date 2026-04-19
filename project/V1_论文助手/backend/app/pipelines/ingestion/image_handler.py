"""图片描述注入：扫描 Markdown 图片引用 → VLM 批量描述 → 回填到 alt text

输出格式：![原始文件名hash | VLM描述](images/xxx.jpg)
切块时整个 ![...](...) 作为一个整体，不会被切断。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re

from app.clients.vlm_client import VLMClient

logger = logging.getLogger("paper-assistant")


async def inject_image_descriptions(
    md_content: str,
    images_dir: str,
    paper_dir: str,
    vlm: VLMClient,
    concurrency: int = 10,
) -> str:
    """扫描 MD 中的图片引用，调用 VLM 生成描述，回填到 alt text"""
    cache = _load_cache(paper_dir)

    pattern = re.compile(r"!\[\]\((images/[^)]+)\)")
    matches = list(pattern.finditer(md_content))
    if not matches:
        return md_content

    # 去重，保持顺序
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []  # (image_ref, image_path)
    for m in matches:
        img_ref = m.group(1)
        if img_ref in seen:
            continue
        seen.add(img_ref)
        img_path = os.path.join(images_dir, os.path.basename(img_ref))
        if os.path.exists(img_path):
            unique.append((img_ref, img_path))

    # 分离缓存命中和需要描述的
    to_describe = [(ref, path) for ref, path in unique if ref not in cache]
    cached_hits = len(unique) - len(to_describe)
    logger.info("图片描述注入: %d 张（缓存命中 %d，需描述 %d）", len(unique), cached_hits, len(to_describe))

    if to_describe:
        sem = asyncio.Semaphore(concurrency)

        async def _describe_batch_group(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
            async with sem:
                paths = [path for _, path in items]
                descs = await vlm.describe_batch(paths)
                return [(items[i][0], descs[i]) for i in range(len(items))]

        # 每批并发组最多 concurrency 个组同时跑
        results = await asyncio.gather(
            *[_describe_batch_group(to_describe[i : i + 5]) for i in range(0, len(to_describe), 5)],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                logger.warning("VLM 批量调用失败: %s", r)
            else:
                for ref, desc in r:
                    cache[ref] = desc

        _save_cache(paper_dir, cache)

    # 回填到 Markdown
    def _replace(m: re.Match) -> str:
        img_ref = m.group(1)
        desc = cache.get(img_ref, "")
        if desc and desc != "description unavailable":
            short_hash = os.path.basename(img_ref)[:8]
            return f"![{short_hash} | {desc}]({img_ref})"
        return m.group(0)

    return pattern.sub(_replace, md_content)


def _load_cache(paper_dir: str) -> dict[str, str]:
    path = os.path.join(paper_dir, "image_descriptions.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_cache(paper_dir: str, cache: dict[str, str]) -> None:
    path = os.path.join(paper_dir, "image_descriptions.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
