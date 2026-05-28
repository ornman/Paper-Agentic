"""VLM 图片语义理解处理器

异步流水线架构：
1. 接收 transformation 产出的图片
2. 异步逐张调用 VLM API
3. 结果写入临时 JSON 文件
4. 等 cleaning 完成后，回填到 markdown
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("paper-assistant")

# VLM 提示词
_SINGLE_PROMPT = (
    "这张图片来自一篇学术论文。请用中文描述图片内容，要求提取关键图示、趋势、数值和图中文字。"
    "直接输出一段简洁描述，不超过200字。"
)

# 分析路由枚举
ANALYSIS_ROUTES = {
    "general_image": "普通插图、照片",
    "technical_diagram": "架构图、流程图",
    "data_visualization": "折线图、柱状图、散点图",
    "form_like": "表单、问卷",
    "formula_like": "公式截图",
    "text_dense_visual": "高文字密度截图",
}

# 兜底描述
FALLBACK_DESCRIPTIONS = {
    "general_image": "[此处包含一张图片，自动描述失败，建议结合原图查看。]",
    "form_like": "[此处包含表单图片，自动描述失败，建议结合原图查看。]",
    "formula_like": "[此处包含公式图片，自动描述失败，建议结合原图查看。]",
    "data_visualization": "[此处包含图表，自动描述失败，建议结合原图查看。]",
}


@dataclass
class ImageAnalysis:
    """单张图片分析结果"""
    image_path: str
    description: str = ""
    analysis_route: str = "general_image"
    status: str = "pending"  # pending / ok / degraded / failed
    error: str | None = None
    attempt_count: int = 0


@dataclass
class VLMResult:
    """VLM 处理结果"""
    task_id: str
    analyses: list[ImageAnalysis]
    temp_json_path: str
    visual_blocks: list[dict] = field(default_factory=list)
    logs: list[dict] = field(default_factory=list)


class VLMProcessor:
    """VLM 处理器

    异步逐张调用 VLM API，结果写入临时 JSON。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.coro0.top/v1",
        model: str = "qwen3-vl:235b",
        max_retries: int = 3,
        base_delay_ms: int = 1000,
        jitter_ms: int = 300,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._max_retries = max_retries
        self._base_delay_ms = base_delay_ms
        self._jitter_ms = jitter_ms

    async def process_images(
        self,
        images: list[dict],
        temp_dir: Path,
        mineru_metadata: dict | None = None,
    ) -> VLMResult:
        """处理图片列表

        Args:
            images: 图片列表 [{"page": int, "path": str}]
            temp_dir: 临时文件目录
            mineru_metadata: MinerU 解析元数据（可选，用于 image_paths 和路由分类）

        Returns:
            VLMResult
        """
        # 优先使用 MinerU metadata 中的 image_paths
        mineru_image_paths = []
        if mineru_metadata:
            mineru_image_paths = mineru_metadata.get("image_paths", [])

        # 如果 MinerU 有 image_paths，转换为 images 格式
        if mineru_image_paths and not images:
            images = [{"page": 0, "path": p} for p in mineru_image_paths]
        import random

        task_id = str(uuid.uuid4())[:8]
        logs: list[dict] = []
        analyses: list[ImageAnalysis] = []

        # 初始化分析结果（带路由分类）
        content_list = (mineru_metadata or {}).get("content_list", [])
        for img in images:
            route = _classify_analysis_route(img["path"], content_list)
            analyses.append(ImageAnalysis(
                image_path=img["path"],
                analysis_route=route,
            ))

        # 逐张异步调用 VLM
        for i, analysis in enumerate(analyses):
            logs.append(_log("info", f"开始处理图片 {i+1}/{len(analyses)}: {analysis.image_path}"))

            for attempt in range(self._max_retries):
                analysis.attempt_count = attempt + 1

                try:
                    description = await self._call_vlm(analysis.image_path)
                    analysis.description = description
                    analysis.status = "ok"
                    logs.append(_log("info", f"图片 {i+1} 描述成功"))
                    break

                except Exception as e:
                    logger.warning("VLM 调用失败 (attempt %d): %s", attempt + 1, e)
                    logs.append(_log("warning", f"VLM 调用失败 (attempt {attempt+1}): {e}"))

                    if attempt < self._max_retries - 1:
                        # 指数退避 + 抖动
                        delay = (self._base_delay_ms * (2 ** attempt) + random.randint(0, self._jitter_ms)) / 1000
                        await asyncio.sleep(delay)
                    else:
                        # 最终失败，使用兜底描述
                        analysis.status = "degraded"
                        analysis.description = FALLBACK_DESCRIPTIONS.get(
                            analysis.analysis_route,
                            FALLBACK_DESCRIPTIONS["general_image"],
                        )
                        analysis.error = str(e)
                        logs.append(_log("warning", f"图片 {i+1} 使用兜底描述"))

        # 保存到临时 JSON
        temp_json_path = temp_dir / f"vlm_{task_id}.json"
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_data = {
            "task_id": task_id,
            "analyses": [
                {
                    "image_path": a.image_path,
                    "description": a.description,
                    "analysis_route": a.analysis_route,
                    "status": a.status,
                    "error": a.error,
                    "attempt_count": a.attempt_count,
                }
                for a in analyses
            ],
        }

        with open(temp_json_path, "w", encoding="utf-8") as f:
            json.dump(temp_data, f, ensure_ascii=False, indent=2)

        logs.append(_log("info", f"VLM 结果已保存到 {temp_json_path}"))

        # 构建 visual_blocks
        visual_blocks = _build_visual_blocks(analyses, content_list)

        return VLMResult(
            task_id=task_id,
            analyses=analyses,
            temp_json_path=str(temp_json_path),
            visual_blocks=visual_blocks,
            logs=logs,
        )

    async def _call_vlm(self, image_path: str) -> str:
        """调用 VLM API"""
        import httpx

        media_type, data = self._encode_image(image_path)

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}},
                                {"type": "text", "text": _SINGLE_PROMPT},
                            ],
                        }
                    ],
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"] or "description unavailable"

    @staticmethod
    def _encode_image(image_path: str) -> tuple[str, str]:
        """编码图片为 base64"""
        _MEDIA_TYPE_MAP = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }

        ext = image_path.rsplit(".", 1)[-1].lower()
        media_type = _MEDIA_TYPE_MAP.get(ext, "image/png")
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return media_type, data


def _classify_analysis_route(image_path: str, content_list: list[dict]) -> str:
    """根据 MinerU metadata 分析图片路由

    Args:
        image_path: 图片路径
        content_list: MinerU content_list

    Returns:
        分析路由类型
    """
    img_name = Path(image_path).stem.lower()

    # 在 content_list 中找到对应的图片 block
    for block in content_list:
        block_type = block.get("type", "")
        block_text = block.get("text", "").lower()

        # 匹配图片路径
        block_img = block.get("img_path", "") or block.get("image_path", "")
        if block_img and Path(block_img).stem.lower() == img_name:
            # 根据 block 类型分类
            if block_type == "equation":
                return "formula_like"
            if block_type == "table":
                return "form_like"

        # 根据周围文本分类
        if block_text:
            if any(kw in block_text for kw in ["图", "fig", "figure", "图表", "趋势", "对比"]):
                return "data_visualization"
            if any(kw in block_text for kw in ["架构", "流程", "框架", "结构", "diagram", "flowchart"]):
                return "technical_diagram"
            if any(kw in block_text for kw in ["公式", "equation", "formula"]):
                return "formula_like"

    return "general_image"


def _build_visual_blocks(analyses: list[ImageAnalysis], content_list: list[dict]) -> list[dict]:
    """构建 visual_blocks 输出

    Args:
        analyses: VLM 分析结果列表
        content_list: MinerU content_list

    Returns:
        visual_blocks 列表
    """
    blocks = []
    for analysis in analyses:
        # 找到对应的 content_list block 获取 page/bbox
        page = 0
        bbox = []
        img_name = Path(analysis.image_path).stem.lower()

        for block in content_list:
            block_img = block.get("img_path", "") or block.get("image_path", "")
            if block_img and Path(block_img).stem.lower() == img_name:
                page = block.get("page_idx", 0) + 1
                bbox = block.get("bbox", [])
                break

        blocks.append({
            "image_path": analysis.image_path,
            "description": analysis.description,
            "analysis_route": analysis.analysis_route,
            "page": page,
            "bbox": bbox,
            "parent_anchor_id": "",
        })

    return blocks


def merge_vlm_into_markdown(
    markdown: str,
    vlm_result: VLMResult,
) -> str:
    """将 VLM 描述回填到 markdown

    Args:
        markdown: 清洗后的 markdown
        vlm_result: VLM 处理结果

    Returns:
        回填后的 markdown
    """
    for analysis in vlm_result.analyses:
        # 找到图片引用
        img_path = analysis.image_path
        img_name = Path(img_path).name

        # 匹配 ![...](path) 或 [description](path)
        patterns = [
            re.compile(r"!\[([^\]]*)\]\([^)]*" + re.escape(img_name) + r"[^)]*\)"),
            re.compile(r"\[([^\]]*)\]\([^)]*" + re.escape(img_name) + r"[^)]*\)"),
        ]

        for pattern in patterns:
            match = pattern.search(markdown)
            if match:
                # 替换为 [描述](图片路径)
                replacement = f"[{analysis.description}]({img_path})"
                markdown = markdown[:match.start()] + replacement + markdown[match.end():]
                break

    return markdown


def _log(level: str, message: str, **kwargs) -> dict:
    """生成日志条目"""
    import datetime
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    entry.update(kwargs)
    return entry
