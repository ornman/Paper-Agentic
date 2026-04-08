# 清洗服务
# 阶段1：PDF → 清洗 → JSON 缓存
#
# 清洗管道（v2）：
#   1. 文本提取（PyMuPDF get_text，逐页纯文本）
#   2. 行合并为段落（改进：中文行间不加空格）
#   3. 内容过滤管道（页眉、元数据、公式碎片）
#   4. 参考文献区域检测（两遍扫描）
#   5. 输出清洁段落 + 清洗统计

import re
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Callable
from datetime import datetime
import fitz  # PyMuPDF，用 fitz 别名（官方推荐）


# ============================================================
# 噪音模式定义
# ============================================================

# --- 页眉/页脚文本模式 ---
_HEADER_PATTERNS = [
    # "General．No．158" — 期刊总期号
    re.compile(r"General[．.\s]*No[．.\s]*\d+", re.IGNORECASE),
    # "Vol.XX No.XX"
    re.compile(r"Vol\s*[．.]\s*\d+\s*No\s*[．.]\s*\d+", re.IGNORECASE),
    # 纯页码行 "— 85 —" / "- 3 -"
    re.compile(r"^[—\-–]\s*\d+\s*[—\-–]$"),
]

# --- 栏目名模式（·社会发展与社会建设·）---
_COLUMN_NAME_PATTERN = re.compile(r"·[^·]{2,20}·")

# --- 出版元数据模式 ---
_METADATA_PATTERNS = [
    re.compile(r"文章编号\s*[:：]"),
    re.compile(r"收稿日期\s*[:：]"),
    re.compile(r"基金项目\s*[:：]"),
    re.compile(r"作者简介\s*[:：]"),
    re.compile(r"通讯作者\s*[:：]"),
    re.compile(r"通信作者\s*[:：]"),
    re.compile(r"DOI\s*[:：]", re.IGNORECASE),
    re.compile(r"中图分类号\s*[:：]"),
    re.compile(r"文献标[识志]码\s*[:：]"),
    re.compile(r"修回日期\s*[:：]"),
]

# --- 参考文献模式 ---
_REF_HEADER_PATTERN = re.compile(
    r"^(参\s*考\s*文\s*献|references)\s*$", re.IGNORECASE
)
_REF_ENTRY_PATTERN = re.compile(r"^\s*[［\[]\s*\d+\s*[］\]]")
_BIBLIO_MARKERS = re.compile(
    r"[［\[]\s*[JMDCR]\s*[］\]]"          # [J] [M] 等
    r"|[［\[]\s*EB\s*/\s*OL\s*[］\]]"     # [EB/OL]
    r"|https?://"                           # URL 全形
    r"|\.pdf[,，．.\s]"                     # .pdf 后缀（URL 残片）
    r"|\.html?[,，．.\s]"                   # .html 后缀（URL 残片）
    r"|DOI\s*[:：]",                        # DOI
    re.IGNORECASE,
)


# ============================================================
# 过滤器函数
# 每个接收段落文本，返回噪音类型(str)或 None
# ============================================================

def _check_header(text: str) -> Optional[str]:
    """检测页眉/页脚文本模式"""
    for p in _HEADER_PATTERNS:
        if p.search(text):
            return "header"
    return None


def _check_column_name(text: str) -> Optional[str]:
    """
    检测纯栏目名段落（如 "·社会发展与社会建设·"）
    只有栏目名没有其他实质内容时才标记
    """
    stripped = _COLUMN_NAME_PATTERN.sub("", text).strip()
    if _COLUMN_NAME_PATTERN.search(text) and len(stripped) < 10:
        return "column_name"
    return None


def _check_metadata(text: str) -> Optional[str]:
    """
    检测出版元数据（文章编号/收稿日期/基金项目等）

    只在以下情况触发：
    - 元数据模式出现在段落开头（前 50 字符内），说明段落以元数据开头
    - 或段落较短（< 150 字符），说明段落本身就是元数据

    为什么要限制位置：
    摘要和"中图分类号"等经常被 get_text() 合并到同一段落中，
    如果不限制位置，"摘要...中图分类号:C912" 会被整段误杀。
    """
    for p in _METADATA_PATTERNS:
        match = p.search(text)
        if match:
            # 元数据在开头位置，或段落本身就是元数据（较短）
            if match.start() < 50 or len(text) < 150:
                return "metadata"
    return None


def _check_formula_fragment(text: str) -> Optional[str]:
    """
    检测公式碎片

    判据：段落较短（< 200 字符）+ 数学符号占比高 + 中文占比低
    为什么需要两个条件：避免把"含公式的正常段落"误杀
    """
    if len(text) > 200:
        return None
    total = len(text)
    if total == 0:
        return None

    math_symbols = set("+-×÷=≈≠≤≥<>∑∫∏√∞∂∇∈∉⊂⊃∪∩∧∨¬∀∃←→↑↓↔⇒⇔")
    math_count = sum(1 for c in text if c in math_symbols or c.isdigit())
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")

    math_ratio = math_count / total
    cjk_ratio = cjk_count / total

    # 数学符号占比高 + 中文占比低 → 公式碎片
    if math_ratio > 0.3 and cjk_ratio < 0.2:
        return "formula"
    return None


# ============================================================
# 主服务类
# ============================================================

class CleaningService:
    """PDF 清洗服务，输出 JSON 缓存"""

    # 内容过滤管道：顺序执行，命中即停
    # 参考文献用两遍扫描单独处理，不在管道里
    _CONTENT_FILTERS: List[Callable[[str], Optional[str]]] = [
        _check_header,
        _check_column_name,
        _check_metadata,
        _check_formula_fragment,
    ]

    # 段落最小有效长度（字符数）
    _MIN_PARA_LENGTH = 50

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 公开 API（与 ingest_workflow / embedding / indexing 兼容）
    # ============================================================

    def clean_pdf(self, pdf_path: str, document_id: Optional[str] = None) -> Dict:
        """
        清洗单个 PDF，输出 JSON 缓存

        流程：
        1. 逐页 get_text() 提取纯文本
        2. 按行合并为段落（改进：中文不加空格）
        3. 内容过滤（页眉、元数据、栏目名、公式碎片）
        4. 参考文献区域检测
        5. 构建输出 JSON + 清洗统计
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 不存在: {pdf_path}")

        doc_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        doc = fitz.open(pdf_path)

        # 第一步：提取并合并段落
        raw_paragraphs = self._extract_paragraphs(doc)

        # 第二步：过滤噪音 + 参考文献检测
        cleaned, removed_details = self._filter_paragraphs(raw_paragraphs, doc_id)

        page_count = doc.page_count
        doc.close()

        # 构建输出
        cache_data = {
            "document_id": doc_id,
            "source_file": str(pdf_path),
            "source_name": pdf_path.name,
            "page_count": page_count,
            "paragraphs": cleaned,
            "cleaning_stats": {
                "raw_count": len(raw_paragraphs),
                "cleaned_count": len(cleaned),
                "removed_count": len(raw_paragraphs) - len(cleaned),
                "removed_by_type": self._count_by_type(removed_details),
                "purity": round(
                    len(cleaned) / max(len(raw_paragraphs), 1) * 100, 1
                ),
            },
            "metadata": {
                "title": pdf_path.stem,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "status": "cleaned",
                "error": None,
                "retry_count": 0,
            },
        }

        self.save_cache(cache_data)
        return cache_data

    # ============================================================
    # 提取逻辑
    # ============================================================

    def _extract_paragraphs(self, doc) -> List[Dict]:
        """
        从 PDF 提取段落

        策略：使用 get_text() 纯文本模式，然后按行合并。
        为什么不用 get_text("dict")：
        - dict 模式的 block 粒度取决于 PDF 内部结构
        - 两栏排版的中文学术论文中，每行常被拆为独立 block
        - 纯文本模式配合行合并，反而更稳定

        改进点（相比 v1）：
        - 中文行间拼接不再添加空格
        - 短行判断阈值考虑了中文字符宽度
        """
        paragraphs = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()

            # 分行并去空行
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            # 合并行为段落
            current_para_lines = []
            for line in lines:
                # 短行（< 10 字符）可能是标题、编号等，作为段落边界
                if len(line) < 10:
                    if current_para_lines:
                        para_text = self._join_lines(current_para_lines)
                        if len(para_text) > self._MIN_PARA_LENGTH:
                            paragraphs.append({
                                "content": para_text,
                                "page": page_num + 1,
                                "bbox": None,
                                "type": "paragraph",
                            })
                        current_para_lines = []
                else:
                    current_para_lines.append(line)

            # 页末残留
            if current_para_lines:
                para_text = self._join_lines(current_para_lines)
                if len(para_text) > self._MIN_PARA_LENGTH:
                    paragraphs.append({
                        "content": para_text,
                        "page": page_num + 1,
                        "bbox": None,
                        "type": "paragraph",
                    })

        return paragraphs

    def _join_lines(self, lines: List[str]) -> str:
        """
        合并多行为一个段落文本

        规则：
        - 前一行末尾是中文字符，下一行开头是中文字符 → 直接拼接（不加空格）
        - 前一行末尾是英文/数字，下一行开头是英文/数字 → 加空格
        - 其他情况 → 加空格（保守策略，避免粘连）
        """
        if not lines:
            return ""
        if len(lines) == 1:
            return lines[0]

        result = lines[0]
        for line in lines[1:]:
            if not result or not line:
                result += line
                continue

            last_char = result[-1]
            first_char = line[0]

            # 判断是否中文字符或中文标点
            _CJK_END_PUNCT = set("，。、；：！？）】」』\u201d\u300b")
            _CJK_START_PUNCT = set("（【「『\u201c\u300a")
            last_is_cjk = (
                "\u4e00" <= last_char <= "\u9fff"
                or last_char in _CJK_END_PUNCT
            )
            first_is_cjk = (
                "\u4e00" <= first_char <= "\u9fff"
                or first_char in _CJK_START_PUNCT
            )

            if last_is_cjk and first_is_cjk:
                # 中文→中文：不加空格
                result += line
            elif last_is_cjk or first_is_cjk:
                # 中英混合：不加空格（如 "的供给。中央" 跨行）
                result += line
            else:
                # 英文→英文：加空格（如 "Best Value" 跨行）
                result += " " + line

        return result

    # ============================================================
    # 过滤逻辑
    # ============================================================

    def _filter_paragraphs(
        self, raw_paragraphs: List[Dict], doc_id: str
    ) -> tuple[List[Dict], List[Dict]]:
        """
        过滤噪音段落

        两遍处理：
        1. 第一遍：对每个段落跑内容过滤管道
        2. 第二遍：检测参考文献区域边界，标记后续段落

        返回：(保留段落列表, 被移除段落详情列表)
        """
        # --- 第一遍：内容过滤 ---
        annotated = []
        for para in raw_paragraphs:
            content = para["content"]
            noise_type = None

            for filter_fn in self._CONTENT_FILTERS:
                noise_type = filter_fn(content)
                if noise_type:
                    break

            annotated.append({
                **para,
                "_noise_type": noise_type,
            })

        # --- 第二遍：参考文献区域检测 ---
        ref_start = self._find_reference_boundary(annotated)
        if ref_start is not None:
            for i in range(ref_start, len(annotated)):
                if annotated[i]["_noise_type"] is None:
                    annotated[i]["_noise_type"] = "reference"

        # --- 分离保留/移除 ---
        kept = []
        removed = []
        para_index = 0

        for item in annotated:
            noise = item.pop("_noise_type")
            if noise:
                removed.append({
                    "content_preview": item["content"][:100],
                    "noise_type": noise,
                    "page": item["page"],
                })
            else:
                kept.append({
                    "id": f"{doc_id}_para_{para_index:04d}",
                    "content": item["content"],
                    "page": item["page"],
                    "bbox": item.get("bbox"),
                    "type": item.get("type", "paragraph"),
                })
                para_index += 1

        return kept, removed

    def _find_reference_boundary(self, annotated: List[Dict]) -> Optional[int]:
        """
        找到参考文献区域的起始索引

        策略（按优先级）：
        1. 查找明确的"参考文献"标题行
        2. 在文档后半部分查找以 ［1］ 开头的段落（参考文献第一条）
        3. 从末尾反向扫描连续文献条目群

        为什么需要策略2：
        - 很多中文论文的参考文献没有独立的"参考文献"标题行
        - 但几乎都以 [1] 开始编号
        - 限定在后半部分，避免把正文中的 [1] 引用误判
        """
        total = len(annotated)

        # 策略1：查找"参考文献"标题
        for i, para in enumerate(annotated):
            if para["_noise_type"] is not None:
                continue
            if _REF_HEADER_PATTERN.match(para["content"].strip()):
                annotated[i]["_noise_type"] = "reference_header"
                return i + 1

        # 策略2：在后半部分查找 [1] / ［1］ 开头的段落
        half = total // 2
        for i in range(half, total):
            if annotated[i]["_noise_type"] is not None:
                continue
            content = annotated[i]["content"].strip()
            # 匹配 ［1］ 或 [1] 开头
            if re.match(r"^\s*[［\[]\s*1\s*[］\]]", content):
                return i

        # 策略3：从末尾反向扫描连续文献条目（兜底）
        consecutive = 0
        first_ref_idx = None
        gap = 0  # 允许中间有 1 个不匹配的段落（URL 残片等）

        for i in range(total - 1, -1, -1):
            if annotated[i]["_noise_type"] is not None:
                continue

            content = annotated[i]["content"]
            is_ref = (
                _REF_ENTRY_PATTERN.match(content.strip())
                or self._looks_like_bibliography(content)
            )

            if is_ref:
                consecutive += 1
                first_ref_idx = i
                gap = 0
            else:
                gap += 1
                if gap > 1:
                    # 连续 2 个不匹配 → 停止扫描
                    break

        if consecutive >= 2 and first_ref_idx is not None:
            return first_ref_idx

        return None

    def _looks_like_bibliography(self, text: str) -> bool:
        """
        判断文本是否像参考文献条目（没有 [N] 开头但内容是文献）

        特征：
        - 包含期刊标记 [J] [M] [D] [EB/OL] [R] [C]
        - 包含 URL
        - 包含 DOI
        """
        return bool(_BIBLIO_MARKERS.search(text))

    def _count_by_type(self, removed: List[Dict]) -> Dict[str, int]:
        """按噪音类型统计被移除的段落数"""
        counts: Dict[str, int] = {}
        for item in removed:
            t = item["noise_type"]
            counts[t] = counts.get(t, 0) + 1
        return counts

    # ============================================================
    # 缓存管理（保持原有 API 不变）
    # ============================================================

    def load_cache(self, document_id: str) -> Optional[Dict]:
        """加载缓存"""
        cache_file = self.cache_dir / f"{document_id}.json"
        if not cache_file.exists():
            return None
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_cache(self, data: Dict):
        """保存缓存"""
        doc_id = data["document_id"]
        data["metadata"]["updated_at"] = datetime.utcnow().isoformat()
        cache_file = self.cache_dir / f"{doc_id}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_all_cache_status(self) -> Dict[str, int]:
        """获取所有缓存的状态统计"""
        status_count = {
            "cleaned": 0,
            "embedding": 0,
            "indexed": 0,
            "failed": 0,
        }
        for cache_file in self.cache_dir.glob("*.json"):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                status = data["metadata"]["status"]
                if status in status_count:
                    status_count[status] += 1
        return status_count

    def get_cache_by_status(self, status: str) -> List[Dict]:
        """按状态获取缓存列表"""
        results = []
        for cache_file in self.cache_dir.glob("*.json"):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data["metadata"]["status"] == status:
                    results.append(data)
        return results
