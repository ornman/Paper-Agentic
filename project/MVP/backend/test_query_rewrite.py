#!/usr/bin/env python
"""
Query 改写测试
测试 4 种场景的改写效果，只消耗 LLM 额度。
"""
import asyncio
from app.services.query_rewrite_service import QueryRewriteService
from app.models.query import QueryContext


async def main():
    service = QueryRewriteService()

    # ============ 场景 1：仅 prompt ============
    print("=" * 60)
    print("场景 1：仅 prompt")
    print("=" * 60)
    query = "城乡公共文化服务有什么差距？怎么改善？"
    result = await service.rewrite(query)
    print(f"原始: {query}")
    print(f"改写: {result}")

    # ============ 场景 2：仅已写内容 ============
    print(f"\n{'=' * 60}")
    print("场景 2：仅已写内容（推断续写意图）")
    print("=" * 60)
    context2 = QueryContext(
        written_content=(
            "城乡公共文化服务均等化是实现基本公共服务均等化的重要内容。"
            "当前，我国城乡公共文化服务在设施建设、人才配置、资金投入等方面仍存在较大差距。"
            "从设施来看，城市公共文化设施覆盖率远高于农村；"
            "从人才来看，基层文化工作者数量不足、专业素质有待提高。"
        ),
    )
    result2 = await service.rewrite("", context2)
    print(f"已写内容: {context2.written_content[:80]}...")
    print(f"改写: {result2}")

    # ============ 场景 3：已写 + 圈选 ============
    print(f"\n{'=' * 60}")
    print("场景 3：已写内容 + 圈选文本")
    print("=" * 60)
    context3 = QueryContext(
        written_content="数字技术为公共文化服务的创新发展提供了新的路径和可能。",
        selected_text="5G、VR、数字孪生等新兴技术在公共文化服务领域的应用日益广泛",
    )
    result3 = await service.rewrite("", context3)
    print(f"已写: {context3.written_content[:50]}...")
    print(f"圈选: {context3.selected_text}")
    print(f"改写: {result3}")

    # ============ 场景 4：已写 + 圈选 + prompt ============
    print(f"\n{'=' * 60}")
    print("场景 4：已写 + 圈选 + prompt（完整输入）")
    print("=" * 60)
    context4 = QueryContext(
        written_content="数字技术为公共文化服务的创新发展提供了新的路径和可能。",
        selected_text="5G、VR、数字孪生等新兴技术",
        prompt="这些技术在乡村公共文化服务中有哪些具体应用案例？",
    )
    result4 = await service.rewrite("这些技术在乡村公共文化服务中有哪些具体应用案例？", context4)
    print(f"已写: {context4.written_content[:50]}...")
    print(f"圈选: {context4.selected_text}")
    print(f"prompt: {context4.prompt}")
    print(f"改写: {result4}")

    print(f"\n{'=' * 60}")
    print("全部场景测试完成")


if __name__ == "__main__":
    asyncio.run(main())
