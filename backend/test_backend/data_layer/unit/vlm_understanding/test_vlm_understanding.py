"""VLM Understanding 模块测试

VLM-U01: 模块 API 导入
VLM-U02: 内部函数契约
"""

from __future__ import annotations

import pytest
import base64
import tempfile
from pathlib import Path

from app.data_layer.preprocessing.vlm_understanding import (
    VLMProcessor,
    VLMResult,
    ImageAnalysis,
    merge_vlm_into_markdown,
    process_images,
    ANALYSIS_ROUTES,
    FALLBACK_DESCRIPTIONS,
)


class TestVLMU01:
    """模块 API 导入"""

    def test_process_images_is_callable(self):
        """transfer 能拿到可调用入口"""
        assert callable(process_images)

    def test_vlm_processor_importable(self):
        """VLMProcessor 可导入"""
        assert VLMProcessor is not None

    def test_merge_vlm_into_markdown_importable(self):
        """merge_vlm_into_markdown 可导入"""
        assert callable(merge_vlm_into_markdown)


class TestVLMU02:
    """内部函数契约"""

    def test_encode_image(self, tmp_dir):
        """_encode_image 编码图片为 base64"""
        # 创建一个最小 PNG 文件
        png_path = tmp_dir / "test.png"
        # 最小 PNG: 8-byte signature + IHDR + IEND
        minimal_png = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
            b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00"
            b"\x00\x00\x00IEND\xaeB`\x82"
        )
        png_path.write_bytes(minimal_png)

        media_type, data = VLMProcessor._encode_image(str(png_path))
        assert media_type == "image/png"
        # base64 解码后应该和原始数据一致
        decoded = base64.b64decode(data)
        assert decoded == minimal_png

    def test_encode_image_unknown_extension(self, tmp_dir):
        """未知扩展名默认为 PNG"""
        img_path = tmp_dir / "test.xyz"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        media_type, _ = VLMProcessor._encode_image(str(img_path))
        assert media_type == "image/png"

    def test_fallback_descriptions_exist(self):
        """兜底描述存在"""
        assert "general_image" in FALLBACK_DESCRIPTIONS
        assert "form_like" in FALLBACK_DESCRIPTIONS
        assert "formula_like" in FALLBACK_DESCRIPTIONS
        assert "data_visualization" in FALLBACK_DESCRIPTIONS

    def test_analysis_routes_exist(self):
        """分析路由存在"""
        assert "general_image" in ANALYSIS_ROUTES
        assert "technical_diagram" in ANALYSIS_ROUTES

    def test_image_analysis_dataclass(self):
        """ImageAnalysis 数据结构"""
        analysis = ImageAnalysis(image_path="/tmp/test.png")
        assert analysis.status == "pending"
        assert analysis.attempt_count == 0
        assert analysis.description == ""

    def test_merge_vlm_into_markdown(self):
        """VLM 描述回填到 markdown"""
        vlm_result = VLMResult(
            task_id="test",
            analyses=[
                ImageAnalysis(
                    image_path="/tmp/fig1.png",
                    description="这是一个柱状图",
                    status="ok",
                ),
            ],
            temp_json_path="",
        )
        markdown = "![图1](fig1.png)"
        merged = merge_vlm_into_markdown(markdown, vlm_result)
        assert "这是一个柱状图" in merged

    @pytest.mark.asyncio
    async def test_process_images_empty_list(self):
        """空图片列表返回空结果"""
        result = await process_images([])
        assert isinstance(result, VLMResult)
        assert len(result.analyses) == 0

    @pytest.mark.asyncio
    async def test_process_images_no_api_key_raises(self, tmp_dir):
        """无 API key 时抛出 ValueError"""
        # 创建一个最小图片文件
        png_path = tmp_dir / "test.png"
        png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        with pytest.raises(ValueError, match="VLM API key 未配置"):
            await process_images(
                [{"page": 1, "path": str(png_path)}],
                temp_dir=tmp_dir,
                api_key="",  # 显式传空
            )
