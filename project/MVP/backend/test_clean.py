#!/usr/bin/env python
"""
阶段 1 测试：PDF 清洗
只测清洗服务，不涉及 Embedding / 索引 / API 调用。
用一个 PDF 跑一遍，看段落提取和噪音过滤效果。
"""
import json
import shutil
from pathlib import Path
from app.services.cleaning_service import CleaningService


def main():
    # ---------- 配置 ----------
    # 三个测试目录，取第一个目录的第一个 PDF
    paper_dirs = [
        Path("D:/同步/project/MVP/data/papers/城乡公共文化服务的现实发展和演化"),
        Path("D:/同步/project/MVP/data/papers/城乡一体化治理的溯源和内生逻辑"),
        Path("D:/同步/project/MVP/data/papers/数字孪生技术在公共文化服务中的应用"),
    ]
    cache_dir = Path("./data/cache")

    # 清空旧缓存，干净起步
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    print(f"缓存目录: {cache_dir.resolve()}\n")

    # 从第一个目录取一个 PDF
    test_dir = paper_dirs[0]
    pdf_files = sorted(test_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"目录里没有 PDF: {test_dir}")
        return

    test_pdf = pdf_files[0]
    print(f"测试文件: {test_pdf.name}")
    print(f"文件大小: {test_pdf.stat().st_size / 1024:.0f} KB")

    # ---------- 执行清洗 ----------
    service = CleaningService(cache_dir)

    try:
        result = service.clean_pdf(str(test_pdf))
    except Exception as e:
        print(f"\n清洗失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ---------- 输出结果 ----------
    doc_id = result["document_id"]
    paragraphs = result["paragraphs"]
    stats = result["cleaning_stats"]

    print(f"\n{'='*60}")
    print(f"文档 ID: {doc_id}")
    print(f"页数: {result['page_count']}")
    print(f"{'='*60}")

    print(f"\n--- 清洗统计 ---")
    print(f"原始段落数: {stats['raw_count']}")
    print(f"保留段落数: {stats['cleaned_count']}")
    print(f"移除段落数: {stats['removed_count']}")
    print(f"纯净度: {stats['purity']}%")
    print(f"按类型移除: {json.dumps(stats['removed_by_type'], ensure_ascii=False, indent=2)}")

    print(f"\n--- 保留段落（前 5 个）---")
    for i, para in enumerate(paragraphs[:5]):
        content = para["content"]
        preview = content[:100] + ("..." if len(content) > 100 else "")
        print(f"\n  [{i+1}] id={para['id']}  page={para['page']}  len={len(content)}")
        print(f"      {preview}")

    # 确认缓存文件已写入
    cache_file = cache_dir / f"{doc_id}.json"
    if cache_file.exists():
        size_kb = cache_file.stat().st_size / 1024
        print(f"\n缓存文件: {cache_file} ({size_kb:.1f} KB)")
    else:
        print(f"\n缓存文件未找到！")

    print(f"\n阶段 1 完成。")


if __name__ == "__main__":
    main()
