"""真 API 端到端测试

VLM: moonshotai/kimi-k2.6 和 qwen3-vl:235b（via api.coro0.top）
Embedding: SiliconFlow Qwen3-Embedding-4B（强制 1536 维）

运行: uv run pytest tests/data_layer/test_real_api.py -v -s
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import pytest
import httpx

# ── API 配置（从环境变量读取） ────────────────────────────
AGGREGATION_TOKEN = os.environ.get("AGGREGATION_TOKEN", "")
AGGREGATION_BASE = "https://api.coro0.top/v1"

SILICONFLOW_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE = "https://api.siliconflow.cn/v1"

VLM_MODELS = ["moonshotai/kimi-k2.6", "qwen3-vl:235b"]
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-4B"
EMBEDDING_DIMENSIONS = 1536


# ── 辅助函数 ──────────────────────────────────────────────
def _create_test_image_base64() -> tuple[str, str]:
    """创建一个简单的测试图片（红色 100x100 PNG）并返回 (media_type, base64_data)"""
    # 最小 PNG: 1x1 红色像素
    import struct
    import zlib

    def _create_minimal_png() -> bytes:
        """创建一个 100x100 红色 PNG"""
        width, height = 100, 100
        # IHDR
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # IDAT (raw pixel data: each row is filter byte + RGB pixels)
        raw_rows = []
        for _ in range(height):
            row = b"\x00" + b"\xff\x00\x00" * width  # filter=none, red pixels
            raw_rows.append(row)
        raw_data = b"".join(raw_rows)
        compressed = zlib.compress(raw_data)
        idat_crc = zlib.crc32(b"IDAT" + compressed)
        idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)

        # IEND
        iend_crc = zlib.crc32(b"IEND")
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend

    png_bytes = _create_minimal_png()
    return "image/png", base64.b64encode(png_bytes).decode()


# ── VLM 测试 ──────────────────────────────────────────────
class TestVLMRealAPI:
    """VLM 真实 API 测试"""

    @pytest.mark.parametrize("model", VLM_MODELS)
    def test_vlm_call(self, model):
        """调用 VLM API 并验证返回"""
        if not AGGREGATION_TOKEN:
            pytest.skip("需要 AGGREGATION_TOKEN 环境变量")
        if model == "moonshotai/kimi-k2.6":
            pytest.xfail("moonshotai/kimi-k2.6 在聚合站超时（可能不可用）")
        media_type, b64_data = _create_test_image_base64()

        async def _call():
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{AGGREGATION_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AGGREGATION_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64_data}"}},
                                    {"type": "text", "text": "这张图片是什么颜色？用中文简短回答。"},
                                ],
                            }
                        ],
                        "max_tokens": 256,
                    },
                )
                return resp

        resp = asyncio.run(_call())

        print(f"\n{'='*60}")
        print(f"模型: {model}")
        print(f"状态码: {resp.status_code}")

        if resp.status_code != 200:
            print(f"响应: {resp.text[:500]}")

        assert resp.status_code == 200, f"VLM API 调用失败: {resp.status_code}"

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print(f"回复: {content}")
        print(f"{'='*60}")

        assert content, "VLM 返回内容为空"
        assert len(content) > 0

    @pytest.mark.parametrize("model", VLM_MODELS)
    def test_vlm_academic_prompt(self, model):
        """模拟学术论文图片描述场景"""
        if not AGGREGATION_TOKEN:
            pytest.skip("需要 AGGREGATION_TOKEN 环境变量")
        if model == "moonshotai/kimi-k2.6":
            pytest.xfail("moonshotai/kimi-k2.6 在聚合站超时（可能不可用）")
        media_type, b64_data = _create_test_image_base64()
        prompt = "这张图片来自一篇学术论文。请用中文描述图片内容，要求提取关键图示、趋势、数值和图中文字。直接输出一段简洁描述，不超过200字。"

        async def _call():
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{AGGREGATION_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AGGREGATION_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64_data}"}},
                                    {"type": "text", "text": prompt},
                                ],
                            }
                        ],
                        "max_tokens": 512,
                    },
                )
                return resp

        resp = asyncio.run(_call())

        print(f"\n{'='*60}")
        print(f"模型: {model}")
        print(f"状态码: {resp.status_code}")

        assert resp.status_code == 200, f"VLM API 调用失败: {resp.status_code}"

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print(f"学术描述: {content}")
        print(f"{'='*60}")

        assert content


# ── Embedding 测试 ─────────────────────────────────────────
class TestEmbeddingRealAPI:
    """Embedding 真实 API 测试"""

    def test_embedding_single(self):
        """单条文本 embedding"""
        if not SILICONFLOW_KEY:
            pytest.skip("需要 SILICONFLOW_API_KEY 环境变量")
        async def _call():
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{SILICONFLOW_BASE}/embeddings",
                    headers={
                        "Authorization": f"Bearer {SILICONFLOW_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": "深度学习在自然语言处理中的应用",
                        "dimensions": EMBEDDING_DIMENSIONS,
                    },
                )
                return resp

        resp = asyncio.run(_call())

        print(f"\n{'='*60}")
        print(f"Embedding 单条测试")
        print(f"状态码: {resp.status_code}")

        assert resp.status_code == 200, f"Embedding API 调用失败: {resp.status_code}"

        data = resp.json()
        embedding = data["data"][0]["embedding"]
        print(f"向量维度: {len(embedding)}")
        print(f"前5个值: {embedding[:5]}")
        print(f"{'='*60}")

        assert len(embedding) == EMBEDDING_DIMENSIONS, f"维度不匹配: 期望 {EMBEDDING_DIMENSIONS}, 实际 {len(embedding)}"

    def test_embedding_batch(self):
        """批量文本 embedding"""
        if not SILICONFLOW_KEY:
            pytest.skip("需要 SILICONFLOW_API_KEY 环境变量")
        texts = [
            "深度学习在自然语言处理中的应用",
            "机器学习与计算机视觉综述",
            "强化学习算法在游戏中的应用",
        ]

        async def _call():
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{SILICONFLOW_BASE}/embeddings",
                    headers={
                        "Authorization": f"Bearer {SILICONFLOW_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": texts,
                        "dimensions": EMBEDDING_DIMENSIONS,
                    },
                )
                return resp

        resp = asyncio.run(_call())

        print(f"\n{'='*60}")
        print(f"Embedding 批量测试")
        print(f"状态码: {resp.status_code}")

        assert resp.status_code == 200, f"Embedding API 调用失败: {resp.status_code}"

        data = resp.json()
        embeddings = data["data"]
        print(f"返回数量: {len(embeddings)}")

        for i, emb in enumerate(embeddings):
            vec = emb["embedding"]
            print(f"  文本{i}: 维度={len(vec)}, 前3值={vec[:3]}")
            assert len(vec) == EMBEDDING_DIMENSIONS

        print(f"{'='*60}")

    def test_embedding_dimensions_enforced(self):
        """验证强制 1536 维度"""
        if not SILICONFLOW_KEY:
            pytest.skip("需要 SILICONFLOW_API_KEY 环境变量")
        async def _call():
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{SILICONFLOW_BASE}/embeddings",
                    headers={
                        "Authorization": f"Bearer {SILICONFLOW_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": "测试维度",
                        "dimensions": 1536,
                    },
                )
                return resp

        resp = asyncio.run(_call())
        assert resp.status_code == 200

        data = resp.json()
        dim = len(data["data"][0]["embedding"])
        print(f"\n强制维度测试: {dim}")
        assert dim == 1536, f"维度不匹配: {dim}"


# ── 清洗质量测试 ──────────────────────────────────────────
class TestCleaningQuality:
    """清洗质量验证（基于真实 PDF 解析数据）"""

    def _get_cleaner(self):
        """导入 cleaner 模块（用 exec 绕过 dataclass 模块解析问题）"""
        ns = {}
        exec(open("app/data_layer/PDF_preprocessor_data/cleaning/markdown_cleaner.py", encoding="utf-8").read(), ns)
        return ns["clean_markdown"]

    def _find_paper(self, name_fragment: str):
        """找到测试论文目录"""
        from pathlib import Path
        data_dir = Path("tests/_legacy/data_UnitTest")
        for d in data_dir.iterdir():
            if name_fragment in d.name:
                return d
        return None

    def test_cleaning_2018(self):
        """2018 乡村振兴：清洗质量验证"""
        clean_markdown = self._get_cleaner()
        paper = self._find_paper("2018")
        if not paper:
            pytest.skip("2018 论文不存在")

        text = (paper / "converted.md").read_text(encoding="utf-8")
        result = clean_markdown(text)

        lines = result.markdown.split("\n")
        non_empty = [l for l in lines if l.strip()]

        print(f"\n{'='*60}")
        print(f"2018 乡村振兴 清洗结果:")
        print(f"  原始: {len(text)} chars, {text.count(chr(10))} lines")
        print(f"  清洗: {len(result.markdown)} chars, {len(lines)} lines")
        print(f"  非空行: {len(non_empty)}")
        print(f"  缩减比: {result.stats['reduction_ratio']*100:.1f}%")
        print(f"  日志: {[l['message'] for l in result.logs]}")

        # 应该移除页眉页脚
        assert "第 1 页" not in result.markdown
        assert "第 2 页" not in result.markdown

        # 应该保留核心内容
        assert "乡村振兴" in result.markdown
        assert "中共中央国务院" in result.markdown

        print(f"  验证: 页眉已移除, 核心内容已保留")
        print(f"{'='*60}")

    def test_cleaning_liuwei(self):
        """刘威论文：碎片行合并验证"""
        clean_markdown = self._get_cleaner()
        paper = self._find_paper("刘威")
        if not paper:
            pytest.skip("刘威论文不存在")

        text = (paper / "converted.md").read_text(encoding="utf-8")
        result = clean_markdown(text)

        original_lines = text.count("\n")
        cleaned_lines = result.markdown.count("\n")

        print(f"\n{'='*60}")
        print(f"刘威论文 清洗结果:")
        print(f"  原始: {len(text)} chars, {original_lines} lines")
        print(f"  清洗: {len(result.markdown)} chars, {cleaned_lines} lines")
        print(f"  缩减比: {result.stats['reduction_ratio']*100:.1f}%")

        # 应该大幅减少行数（从 7703 降到 < 2000）
        reduction = 1 - cleaned_lines / max(original_lines, 1)
        print(f"  行数缩减: {reduction*100:.1f}%")
        assert cleaned_lines < 2000, f"行数仍然太多: {cleaned_lines}"

        print(f"  验证: 行数已大幅减少")
        print(f"{'='*60}")

    def test_cleaning_vr(self):
        """VR论文：表格残留和 PUA 字符清理验证"""
        clean_markdown = self._get_cleaner()
        paper = self._find_paper("VR")
        if not paper:
            pytest.skip("VR论文不存在")

        text = (paper / "converted.md").read_text(encoding="utf-8")
        result = clean_markdown(text)

        print(f"\n{'='*60}")
        print(f"VR论文 清洗结果:")
        print(f"  原始: {len(text)} chars, {text.count(chr(10))} lines")
        print(f"  清洗: {len(result.markdown)} chars, {result.markdown.count(chr(10))} lines")
        print(f"  缩减比: {result.stats['reduction_ratio']*100:.1f}%")

        # PUA 字符应该被移除
        import re
        pua_count = len(re.findall(r"[-]", result.markdown))
        print(f"  残留 PUA 字符: {pua_count}")
        assert pua_count == 0, f"仍有 {pua_count} 个 PUA 字符"

        # 应该有实质内容
        assert len(result.markdown) > 1000

        print(f"  验证: PUA 字符已清除, 有实质内容")
        print(f"{'='*60}")

    def test_cleaning_gaoqingpan(self):
        """郜清攀论文：清洗质量验证"""
        clean_markdown = self._get_cleaner()
        paper = self._find_paper("郜清攀")
        if not paper:
            pytest.skip("郜清攀论文不存在")

        text = (paper / "converted.md").read_text(encoding="utf-8")
        result = clean_markdown(text)

        print(f"\n{'='*60}")
        print(f"郜清攀论文 清洗结果:")
        print(f"  原始: {len(text)} chars, {text.count(chr(10))} lines")
        print(f"  清洗: {len(result.markdown)} chars, {result.markdown.count(chr(10))} lines")
        print(f"  缩减比: {result.stats['reduction_ratio']*100:.1f}%")

        # 应该保留核心内容
        assert "乡村振兴" in result.markdown
        assert "乡镇政府" in result.markdown

        # PUA 字符应该被移除
        import re
        pua_count = len(re.findall(r"[-]", result.markdown))
        print(f"  残留 PUA: {pua_count}")
        assert pua_count == 0

        print(f"  验证: 核心内容保留, PUA 已清除")
        print(f"{'='*60}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
