"""批量导入测试脚本 - 导入10个PDF验证完整工作流"""

import asyncio
import time
from pathlib import Path

import httpx

# API 基础地址
BASE_URL = "http://localhost:8001/api/v1"

# 选择10个测试PDF（覆盖不同主题）
TEST_PDFS = [
    # 城乡一体化治理主题（5个）
    r"D:\真项目\论文助手\project\MVP\data\papers\城乡一体化治理的溯源和内生逻辑\城乡一体化进程中的乡村治理创新_徐勇.pdf",
    r"D:\真项目\论文助手\project\MVP\data\papers\城乡一体化治理的溯源和内生逻辑\新常态下中国城乡一体化格局及推进战略_魏后凯.pdf",
    r"D:\真项目\论文助手\project\MVP\data\papers\城乡一体化治理的溯源和内生逻辑\论土地整治与乡村空间重构_龙花楼.pdf",
    r"D:\真项目\论文助手\project\MVP\data\papers\城乡一体化治理的溯源和内生逻辑\变中的不变：城乡融合发展的演进逻辑、共性规律及优化路径_贾晋.pdf",
    r"D:\真项目\论文助手\project\MVP\data\papers\城乡一体化治理的溯源和内生逻辑\中国式现代化视域下城乡融合发展的生成逻辑、科学内涵和实践路径_王玲玲.pdf",

    # 数字孪生/公共文化服务主题（5个）
    r"D:\真项目\论文助手\project\MVP\data\papers\数字孪生技术在公共文化服务中的应用\数字赋能农村公共文化服务高质量供给：价值意蕴、动力机制与路径创新_邵明华.pdf",
    r"D:\真项目\论文助手\project\MVP\data\papers\数字孪生技术在公共文化服务中的应用\以数字化促进基本公共文化服务均等化的实践研究_肖希明.pdf",
    r"D:\真项目\论文助手\project\MVP\data\papers\数字孪生技术在公共文化服务中的应用\数字化赋能公共文化服务体系高质量发展：逻辑、困境与路径_杨博.pdf",
    r"D:\真项目\论文助手\project\MVP\data\papers\数字孪生技术在公共文化服务中的应用\基于认知层次动态演化视角的智慧公共文化服务实现策略研究_徐文哲.pdf",
    r"D:\真项目\论文助手\project\MVP\data\papers\数字孪生技术在公共文化服务中的应用\5G驱动的公共数字文化服务智慧化转型_完颜邓邓.pdf",
]


async def import_pdf(client: httpx.AsyncClient, file_path: str, index: int) -> dict:
    """导入单个PDF"""
    pdf_name = Path(file_path).stem
    print(f"\n[{index+1}/10] 开始导入: {pdf_name}")

    start_time = time.time()

    try:
        response = await client.post(
            f"{BASE_URL}/library/import-path",
            json={
                "file_path": file_path,
                "index_mode": "distributed",
                "title": pdf_name,
            },
            timeout=600.0,  # 10分钟超时（MinerU + VLM + Embedding）
        )
        response.raise_for_status()
        result = response.json()

        elapsed = time.time() - start_time
        print(f"✓ 成功 | 耗时: {elapsed:.1f}s | 状态: {result['data']['status']}")

        return {
            "success": True,
            "file": pdf_name,
            "document_id": result["data"]["document_id"],
            "status": result["data"]["status"],
            "elapsed": elapsed,
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"✗ 失败 | 耗时: {elapsed:.1f}s | 错误: {str(e)[:100]}")
        return {
            "success": False,
            "file": pdf_name,
            "error": str(e),
            "elapsed": elapsed,
        }


async def main():
    """批量导入主函数"""
    print("=" * 60)
    print("批量PDF导入测试（10个文件）")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=600.0) as client:
        # 先检查服务健康
        health = await client.get(f"{BASE_URL}/health/")
        print(f"\n服务状态: {health.json()['data']['status']}")

        # 串行导入（避免并发压力）
        results = []
        total_start = time.time()

        for i, pdf_path in enumerate(TEST_PDFS):
            # 检查文件是否存在
            if not Path(pdf_path).exists():
                print(f"[{i+1}/10] 跳过（文件不存在）: {pdf_path}")
                continue

            result = await import_pdf(client, pdf_path, i)
            results.append(result)

            # 每次导入后稍作休息
            await asyncio.sleep(2)

        total_elapsed = time.time() - total_start

        # 统计结果
        print("\n" + "=" * 60)
        print("批量导入测试完成")
        print("=" * 60)

        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count

        print(f"\n总计: {len(results)} 个文件")
        print(f"成功: {success_count} 个")
        print(f"失败: {fail_count} 个")
        print(f"总耗时: {total_elapsed:.1f}s")

        if success_count > 0:
            avg_time = sum(r["elapsed"] for r in results if r["success"]) / success_count
            print(f"平均耗时: {avg_time:.1f}s/文件")

        # 详细结果
        print("\n详细结果:")
        for r in results:
            status = "✓" if r["success"] else "✗"
            print(f"{status} {r['file']} - {r.get('status', r.get('error', '未知'))}")

        # 获取当前文档列表
        print("\n当前文档库状态:")
        docs_resp = await client.get(f"{BASE_URL}/library/documents/")
        docs = docs_resp.json()["data"]
        print(f"文档总数: {len(docs)}")

        # 按状态统计
        status_count = {}
        for doc in docs:
            status = doc["status"]
            status_count[status] = status_count.get(status, 0) + 1

        print("状态分布:")
        for status, count in status_count.items():
            print(f"  {status}: {count} 个")


if __name__ == "__main__":
    asyncio.run(main())
