#!/usr/bin/env python
"""
阶段 2+3 测试：完整导入流程（清洗 → Embedding → 索引）
用 1 个 PDF 跑完三阶段全流程，验证 API 调用和数据库写入。
"""
import asyncio
import shutil
from pathlib import Path
from app.services.ingest_workflow import IngestWorkflow


async def main():
    # ---------- 配置 ----------
    cache_dir = "./data/cache"
    test_pdf_dir = Path("D:/同步/project/MVP/data/papers/城乡公共文化服务的现实发展和演化")
    pdf_files = sorted(test_pdf_dir.glob("*.pdf"))

    if not pdf_files:
        print("没有找到 PDF 文件")
        return

    test_pdf = pdf_files[0]
    print(f"测试文件: {test_pdf.name}")
    print(f"文件大小: {test_pdf.stat().st_size / 1024:.0f} KB\n")

    # 清空旧缓存和索引
    cache_path = Path(cache_dir)
    if cache_path.exists():
        shutil.rmtree(cache_path)

    chroma_path = Path("./data/chroma")
    if chroma_path.exists():
        shutil.rmtree(chroma_path)

    bm25_path = Path("./data/bm25_index.json")
    if bm25_path.exists():
        bm25_path.unlink()

    print("已清空旧缓存/索引\n")

    # ---------- 执行三阶段 ----------
    workflow = IngestWorkflow(cache_dir=cache_dir)

    try:
        result = await workflow.ingest_single_pdf(str(test_pdf))
    except Exception as e:
        print(f"\n导入失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ---------- 验证结果 ----------
    doc_id = result["document_id"]
    paragraphs = result["paragraphs"]
    status = result["metadata"]["status"]

    print(f"\n{'='*60}")
    print(f"文档 ID: {doc_id}")
    print(f"最终状态: {status}")
    print(f"段落数: {len(paragraphs)}")

    # 检查 embedding 是否存在
    has_embedding = all("embedding" in p for p in paragraphs)
    embedding_dim = len(paragraphs[0]["embedding"]) if has_embedding else 0
    print(f"Embedding 存在: {has_embedding}")
    print(f"Embedding 维度: {embedding_dim}")

    # 检查索引状态
    workflow_status = workflow.get_status()
    print(f"\n--- 索引状态 ---")
    print(f"缓存: {workflow_status['cache']}")
    print(f"ChromaDB 向量数: {workflow_status['chroma_count']}")
    print(f"BM25 文档数: {workflow_status['bm25_count']}")

    # 检查文件
    print(f"\n--- 文件检查 ---")
    cache_file = cache_path / f"{doc_id}.json"
    print(f"缓存 JSON: {'存在' if cache_file.exists() else '不存在'}")
    print(f"ChromaDB 目录: {'存在' if chroma_path.exists() else '不存在'}")

    if status == "indexed":
        print(f"\n全流程测试通过！")
    else:
        print(f"\n状态异常，期望 indexed，实际 {status}")


if __name__ == "__main__":
    asyncio.run(main())
