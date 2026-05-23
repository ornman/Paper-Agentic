"""Kimi API 单元测试 - 验证连接和响应.

运行方式:
    cd project/MVP/backend
    KIMI_API_KEY=your_key uv run python tests/test_kimi_api.py

或使用 pytest:
    uv run pytest tests/test_kimi_api.py -v
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_kimi_chat():
    """测试 Kimi Chat API（纯文本问答）."""
    api_key = "sk-kimi-zgS6HSlZNpKVvVT24x9QD8rG2thvGkNLgzhFJ9IFx8rSi1DdhqCAR4QM0LiSsXez"
    base_url = "https://api.kimi.com/coding/v1"

    payload = {
        "model": "kimi-for-coding",
        "messages": [{"role": "user", "content": "1+1=? 简短回答"}],
        "max_tokens": 50,
    }

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "User-Agent": "claude-code",  # 🔑 关键伪装
    }

    print("🧪 测试 Kimi Chat API...")
    print(f"   URL: {base_url}/messages")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{base_url}/messages", json=payload, headers=headers)
        print(f"   Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []))
            print(f"✅ Chat API 成功！响应: {text[:100]}")
        else:
            print(f"❌ Chat API 失败: {resp.text[:200]}")
            raise AssertionError(f"Status {resp.status_code}")


async def test_kimi_vlm():
    """测试 Kimi VLM API（图片理解）."""
    api_key = "sk-kimi-zgS6HSlZNpKVvVT24x9QD8rG2thvGkNLgzhFJ9IFx8rSi1DdhqCAR4QM0LiSsXez"
    base_url = "https://api.kimi.com/coding/v1"

    # 1x1 红色像素 PNG (base64)
    test_image_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    payload = {
        "model": "kimi-for-coding",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": test_image_b64,
                        },
                    },
                    {"type": "text", "text": "这是什么颜色？简短回答。"},
                ],
            }
        ],
        "max_tokens": 50,
        "temperature": 0.0,
    }

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "User-Agent": "claude-code",  # 🔑 关键伪装
    }

    print("🧪 测试 Kimi VLM API...")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{base_url}/messages", json=payload, headers=headers)
        print(f"   Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []))
            print(f"✅ VLM API 成功！响应: {text[:100]}")
        else:
            print(f"❌ VLM API 失败: {resp.text[:200]}")
            raise AssertionError(f"Status {resp.status_code}")


async def main():
    """运行所有测试."""
    print("=" * 50)
    print("Kimi API 连接测试")
    print("=" * 50)
    print()

    try:
        await test_kimi_chat()
        print()
        await test_kimi_vlm()
        print()
        print("=" * 50)
        print("🎉 所有测试通过！")
        print("=" * 50)
    except AssertionError as e:
        print()
        print("=" * 50)
        print(f"❌ 测试失败: {e}")
        print("=" * 50)
        raise


if __name__ == "__main__":
    asyncio.run(main())
