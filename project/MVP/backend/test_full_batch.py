#!/usr/bin/env python
"""
阶段 2+3 批量测试：批量完整导入
从 3 个目录各取 3 个 PDF，共 9 个，跑完整三阶段流程。
"""
import asyncio
import shutil
from pathlib import Path
from app.services.ingest_workflow import IngestWorkflow


async def main():
    paper_dirs = [
        Path("D:/同步/project/MVP/data/papers/城乡公共文化服务的现实发展和演化"),
        Path("D:/同步/project/MVP/data/papers/城乡一体化治理的溯源和内生逻辑"),
        Path("D:/同步/project/MVP/data/papers/数字孪生技术在公共文化服务中的应用"),
    ]
    cache_dir = "./data/cache"

    # 清空旧数据
    for path in [Path(cache_dir), Path("./data/chroma")]:
        if path.exists():
            shutil.rmtree(path)
    bm25 = Path("./data/bm25_index.json")
    if bm25.exists():
        bm25.unlink()

    # 收集 PDF：每个目录取前 3 个
    pdf_paths = []
    for d in paper_dirs:
        pdfs = sorted(d.glob("*.pdf"))[:3]
        pdf_paths.extend([str(p) for p in pdfs])

    print(f"共 {len(pdf_paths)} 个 PDF，开始批量导入...\n")

    # 执行批量导入
    workflow = IngestWorkflow(cache_dir=cache_dir)
    results = await workflow.batch_ingest(pdf_paths, continue_on_error=True)

    # 汇总
    print(f"\n{'='*60}")
    print(f"总计: {results['total']}")
    print(f"成功: {len(results['success'])}")
    print(f"失败: {len(results['failed'])}")

    if results["failed"]:
        print(f"\n--- 失败详情 ---")
        for f in results["failed"]:
            print(f"  {Path(f['source']).name}: {f['error']}")

    # 最终状态
    status = workflow.get_status()
    print(f"\n--- 最终索引状态 ---")
    print(f"缓存: {status['cache']}")
    print(f"ChromaDB 向量数: {status['chroma_count']}")
    print(f"BM25 文档数: {status['bm25_count']}")


if __name__ == "__main__":
    asyncio.run(main())
