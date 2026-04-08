#!/usr/bin/env python
"""
阶段 1.5 测试：批量清洗稳定性
从 3 个测试目录各取前 3 个 PDF，共 9 个，验证清洗管道不会崩。
"""
import json
import shutil
from pathlib import Path
from app.services.cleaning_service import CleaningService


def main():
    paper_dirs = [
        Path("D:/同步/project/MVP/data/papers/城乡公共文化服务的现实发展和演化"),
        Path("D:/同步/project/MVP/data/papers/城乡一体化治理的溯源和内生逻辑"),
        Path("D:/同步/project/MVP/data/papers/数字孪生技术在公共文化服务中的应用"),
    ]
    cache_dir = Path("./data/cache")

    # 清空旧缓存
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    service = CleaningService(cache_dir)

    # 收集测试 PDF：每个目录取前 3 个
    test_pdfs = []
    for d in paper_dirs:
        pdfs = sorted(d.glob("*.pdf"))[:3]
        test_pdfs.extend(pdfs)

    print(f"共 {len(test_pdfs)} 个测试 PDF\n")

    success = 0
    failed = 0
    total_raw = 0
    total_clean = 0

    for i, pdf in enumerate(test_pdfs, 1):
        try:
            result = service.clean_pdf(str(pdf))
            stats = result["cleaning_stats"]
            total_raw += stats["raw_count"]
            total_clean += stats["cleaned_count"]
            removed = json.dumps(stats["removed_by_type"], ensure_ascii=False)
            print(f"  [{i:2d}] {pdf.name[:50]:<52s}  "
                  f"原={stats['raw_count']:3d} → 留={stats['cleaned_count']:3d}  "
                  f"纯={stats['purity']:5.1f}%  移除={removed}")
            success += 1
        except Exception as e:
            print(f"  [{i:2d}] {pdf.name[:50]:<52s}  失败: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"成功: {success}/{len(test_pdfs)}")
    print(f"失败: {failed}/{len(test_pdfs)}")
    print(f"原始段落总数: {total_raw}")
    print(f"保留段落总数: {total_clean}")
    if total_raw > 0:
        print(f"整体纯净度: {total_clean / total_raw * 100:.1f}%")
    print(f"缓存目录: {cache_dir.resolve()}")
    print(f"缓存文件数: {len(list(cache_dir.glob('*.json')))}")


if __name__ == "__main__":
    main()
