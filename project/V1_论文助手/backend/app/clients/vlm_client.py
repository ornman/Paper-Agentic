"""Kimi VLM 图片理解客户端

必须携带特殊 headers：
  - User-Agent: claude-code
  - anthropic-version: 2023-06-01
"""

from __future__ import annotations

import base64
import json
import logging
import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger("paper-assistant")

_HEADERS = {
    "anthropic-version": "2023-06-01",
    "User-Agent": "claude-code",
    "Content-Type": "application/json",
}

_PROMPT_SINGLE = (
    "这张图片来自一篇学术论文。请用中文描述图片内容，要求："
    "1.流程图/框架图：描述各模块名称和连接关系；"
    "2.数据图表：提取关键数据趋势和数值；"
    "3.截图/照片：描述界面或场景内容；"
    "4.包含文字则准确转录关键文字。"
    "请用一段话简洁描述，不超过200字。直接输出描述，不要加标题或格式。"
)

_BATCH_PROMPT = (
    "以下是来自一篇学术论文的 {count} 张图片（依次编号 1~{count}）。"
    "请对每张图片分别用中文描述，要求："
    "1.流程图/框架图：描述各模块名称和连接关系；"
    "2.数据图表：提取关键数据趋势和数值；"
    "3.截图/照片：描述界面或场景内容；"
    "4.包含文字则准确转录关键文字。"
    "每张用一段话简洁描述，不超过200字。"
    "严格按如下 JSON 数组格式输出，不要输出其他内容：\n"
    '["图片1的描述", "图片2的描述", ...]'
)

_MEDIA_TYPE_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}

_MAX_BATCH_SIZE = 5


class VLMClient:
    """Kimi Coding API 图片描述"""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.kimi_api_key
        self._base_url = settings.kimi_base_url
        self._model = settings.kimi_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_headers(self) -> dict[str, str]:
        return {**_HEADERS, "x-api-key": self._api_key}

    @staticmethod
    def _encode_image(image_path: str) -> tuple[str, str]:
        ext = image_path.rsplit(".", 1)[-1].lower()
        media_type = _MEDIA_TYPE_MAP.get(ext, "image/png")
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return media_type, data

    async def describe_image(
        self,
        image_path: str,
        prompt: str | None = None,
    ) -> str:
        if not self._api_key:
            return "description unavailable"

        media_type, img_data = self._encode_image(image_path)
        body = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_data}},
                        {"type": "text", "text": prompt or _PROMPT_SINGLE},
                    ],
                }
            ],
        }

        try:
            client = await self._get_client()
            resp = await client.post(self._base_url, headers=self._build_headers(), json=body)
            resp.raise_for_status()
            return self._extract_text(resp.json())
        except Exception as e:
            logger.warning("VLM single failed for %s: %s", image_path, e)
            return "description unavailable"

    async def describe_batch(
        self,
        image_paths: list[str],
        batch_size: int = _MAX_BATCH_SIZE,
    ) -> list[str]:
        """批量描述图片，每 batch_size 张打包成一次 API 调用。"""
        if not image_paths:
            return []
        if not self._api_key:
            return ["description unavailable"] * len(image_paths)

        results: list[str | None] = [None] * len(image_paths)
        batches = []
        for i in range(0, len(image_paths), batch_size):
            batches.append((i, image_paths[i : i + batch_size]))

        for offset, batch in batches:
            if len(batch) == 1:
                results[offset] = await self.describe_image(batch[0])
                continue
            descs = await self._call_batch(batch)
            # 检查 batch 结果是否有全盘失败的
            has_failure = any(d == "description unavailable" for d in descs)
            if has_failure:
                # 对失败的逐个单图 fallback
                for j, d in enumerate(descs):
                    if d == "description unavailable":
                        logger.info("Batch fallback to single: %s", batch[j])
                        results[offset + j] = await self.describe_image(batch[j])
                    else:
                        results[offset + j] = d
            else:
                for j, d in enumerate(descs):
                    results[offset + j] = d

        return [r or "description unavailable" for r in results]

    async def _call_batch(self, paths: list[str]) -> list[str]:
        count = len(paths)
        content_blocks: list[dict] = []
        for p in paths:
            media_type, img_data = self._encode_image(p)
            content_blocks.append(
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_data}}
            )
        content_blocks.append({"type": "text", "text": _BATCH_PROMPT.format(count=count)})

        body = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": content_blocks}],
        }

        try:
            client = await self._get_client()
            resp = await client.post(self._base_url, headers=self._build_headers(), json=body)
            resp.raise_for_status()
            text = self._extract_text(resp.json())
            return self._parse_batch_response(text, count)
        except Exception as e:
            logger.warning("VLM batch failed (%d imgs): %s", count, e)
            return ["description unavailable"] * count

    @staticmethod
    def _extract_text(data: dict) -> str:
        content = data.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        if isinstance(content, str):
            return content
        return ""

    @staticmethod
    def _parse_batch_response(text: str, expected: int) -> list[str]:
        # 尝试 JSON 解析
        try:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, list) and len(parsed) == expected:
                    return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
        # JSON 解析失败，按序号分割兜底
        parts = re.split(r"(?:^|\n)\s*\d+[\.\)、]\s*", text)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) == expected:
            return parts
        logger.warning("Batch parse fallback: got %d/%d parts", len(parts), expected)
        return ["description unavailable"] * expected
