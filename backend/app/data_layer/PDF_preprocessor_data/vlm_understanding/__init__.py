"""VLM 图片语义理解模块

异步流水线架构：
1. 接收 transformation 产出的图片
2. 异步逐张调用 VLM API
3. 结果写入临时 JSON 文件
4. 等 cleaning 完成后，回填到 markdown
"""

from __future__ import annotations

from pathlib import Path

from .vlm_processor import (
    VLMProcessor,
    VLMResult,
    ImageAnalysis,
    merge_vlm_into_markdown,
    ANALYSIS_ROUTES,
    FALLBACK_DESCRIPTIONS,
)


async def process_images(
    images: list[dict],
    temp_dir: Path | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    mineru_metadata: dict | None = None,
) -> VLMResult:
    """处理图片列表的便捷入口

    Args:
        images: 图片列表 [{"page": int, "path": str}]
        temp_dir: 临时文件目录，默认使用系统临时目录
        api_key: VLM API key，默认从配置读取
        base_url: VLM base URL，默认从配置读取
        model: VLM 模型名，默认从配置读取
        mineru_metadata: MinerU 解析元数据（可选，用于 image_paths 和路由分类）

    Returns:
        VLMResult
    """
    import tempfile

    # 优先使用 MinerU metadata 中的 image_paths
    if mineru_metadata and not images:
        mineru_image_paths = mineru_metadata.get("image_paths", [])
        if mineru_image_paths:
            images = [{"page": 0, "path": p} for p in mineru_image_paths]

    if not images:
        return VLMResult(task_id="empty", analyses=[], temp_json_path="")

    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vlm_"))

    # 从配置加载参数
    if api_key is None:
        from ...data_persistence.config import load_config
        config = load_config()
        api_key = config.vlm_api_key
        if base_url is None:
            base_url = config.vlm_base_url
        if model is None:
            model = config.vlm_model

    if not api_key:
        raise ValueError("VLM API key 未配置，请设置 VLM_API_KEY 或 My_ProxyAPI_KEY 环境变量")

    processor = VLMProcessor(
        api_key=api_key,
        base_url=base_url or "https://api.coro0.top/v1",
        model=model or "qwen3-vl:235b",
    )
    return await processor.process_images(images, temp_dir, mineru_metadata=mineru_metadata)


__all__ = [
    "VLMProcessor",
    "VLMResult",
    "ImageAnalysis",
    "merge_vlm_into_markdown",
    "process_images",
    "ANALYSIS_ROUTES",
    "FALLBACK_DESCRIPTIONS",
]
