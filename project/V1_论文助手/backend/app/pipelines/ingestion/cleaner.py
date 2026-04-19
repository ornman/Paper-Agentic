"""PDF 清洗器 — Markdown 为主、JSON layout 元数据为辅

MinerU 输出 full.md（主文本）+ layout.json（结构化元数据）+ images/
清洗流程：
1. 读取 Markdown 全文
2. 去除封面、目录、致谢、学术成果等噪音段落
3. 按章节标题切分为语义块
4. 每个语义块附带章节层级信息
5. 用 JSON layout 补充页码信息（可选）
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    content: str
    page: int
    chunk_type: str = "paragraph"
    section_title: str = ""
    section_level: int = 0
    file_hash: str = ""
    source_path: str = ""
    has_image: str = "false"


# ── 噪音检测 ──

# 目录行：含点号引导的页码引用，如 "1.1 背景 ..... 5"
_TOC_LINE = re.compile(r"^[\d.\s]+\S.*?\.+\s*\d+\s*$")
# 封面关键词（学位论文封面、学校名等）
_COVER_KEYWORDS = frozenset({
    "硕士学位论文", "博士学位论文", "学士学位论文", "本科毕业论文",
    "Thesis for Master", "Thesis for Doctor", "Dissertation",
    "Dissertation Submitted", "论文题目", "作者姓名", "培养单位",
    "专业名称", "指导教师", "合作导师", "Candidate:", "College:",
    "Specialty:", "Supervisor:", "Shandong University",
    "学位论文评阅", "答辩委员会",
})
# 学校名（通常封面多行重复）
_SCHOOL_NAMES = frozenset({
    "山东大学", "北京大学", "清华大学", "浙江大学",
    "SHANDONG UNIVERSITY", "PEKING UNIVERSITY", "TSINGHUA UNIVERSITY",
})
# 文末噪音标题
_END_NOISE_SECTIONS = frozenset({
    "致谢", "参考文献", "攻读硕士", "攻读博士", "学位论文评阅",
    "Acknowledgements", "Acknowledgments", "References", "Bibliography",
    "附录", "Appendix", "Appendices",
})
# 短行阈值：少于 4 字且不是数字的行视为碎片
_SHORT_LINE_MAX = 3


def clean_markdown(md_content: str, paper_id: str) -> list[Chunk]:
    """主清洗入口：从 Markdown 提取语义块"""
    lines = md_content.split("\n")

    # Phase 0: 预处理 — 去除 MinerU 目录中的"标题+页码"伪标题
    # 例如 "# 第1章绪论 1" → 目录条目，页码后缀是特征
    # 而 "# 第1章绪论" → 真正的章节标题
    lines = _strip_toc_entries(lines)

    # Phase 1: 识别并标记噪音区域
    zones = _detect_zones(lines)

    # Phase 2: 在有效区域内按章节切分
    chunks = _extract_chunks(lines, zones, paper_id)

    # Phase 3: 过滤残余噪音
    chunks = _filter_noise(chunks)

    return chunks


def _strip_toc_entries(lines: list[str]) -> list[str]:
    """预处理：把目录区的伪标题变成普通行（去掉 # 前缀）

    目录特征：标题后面跟着页码数字，如 "# 第1章绪论 1" 或 "# Chapter 1 Introduction. 1"
    真正的章节标题后面没有数字页码
    """
    # 先找到所有含页码引用的标题行
    toc_heading_pattern = re.compile(
        r"^(#+)\s+(.+?)\s+[\.]+\s*\d+\s*$|"   # "..... 41" 格式
        r"^(#+)\s+(.+?)\s+\.\s*\d+\s*$|"        # ". 1" 格式
        r"^(#+)\s+(.+?)\s+\d{1,3}\s*$"           # " 1" 结尾的短数字
    )

    result = []
    for line in lines:
        m = re.match(r"^(#+)\s+(.+?)\s+(\d{1,3})\s*$", line.strip())
        if m:
            prefix, title, num = m.group(1), m.group(2), m.group(3)
            # 检查这个标题是否在"目录上下文"中
            # 如果 title 包含章节号（第X章、Chapter X）且 num 是页码
            if _is_toc_heading(title, num):
                # 变成普通行（去掉 # 前缀）
                result.append(title)
                continue

        # 页码引用行 "..... 41" 整行删除
        if _TOC_LINE.match(line.strip()):
            result.append("")
            continue

        result.append(line)
    return result


def _is_toc_heading(title: str, trailing_num: str) -> bool:
    """判断一个标题+尾随数字是否是目录条目"""
    # 包含章节号 + 尾随页码
    if re.search(r"第\s*\d+\s*章", title):
        return True
    if re.search(r"(?:Chapter|CHAPTER)\s+\d+", title):
        return True
    if re.search(r"\d+\.\d+", title):  # "1.1 Background"
        return True
    # 通用模式：标题末尾跟着点号和数字 "Abstract (in Chinese) I"
    if re.search(r"\b[IVX]+\s*$", title):
        return True
    return False


# ── Zone 检测 ──

@dataclass
class _Zone:
    start: int
    end: int  # exclusive
    zone_type: str  # "cover", "toc", "end_noise", "body"


def _detect_zones(lines: list[str]) -> list[_Zone]:
    """把文档分成区域：cover_toc / body / end_noise

    策略：
    - 摘要之前的所有内容都是 cover+toc（封面、学校名、中英文目录）
    - 摘要开始到致谢/参考文献之前是 body
    - 参考文献/致谢之后是 end_noise
    """
    n = len(lines)
    zones: list[_Zone] = []

    # 1. 找到摘要开始位置（中英文论文的正文起点）
    body_start = n
    for idx, line in enumerate(lines):
        stripped = line.strip()
        # 中文摘要
        if stripped in ("# 摘要", "## 摘要"):
            body_start = idx
            break
        # 英文 Abstract（纯英文论文）
        if stripped in ("# Abstract", "# ABSTRACT", "## Abstract"):
            if body_start == n:
                body_start = idx

    # 如果找不到摘要，退回到找第一个章节标题
    if body_start == n:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r"^#+\s*第\s*1\s*章", stripped):
                body_start = idx
                break
            if re.match(r"^#+\s*(?:Chapter|CHAPTER|Introduction)\s+1\b", stripped):
                body_start = idx
                break
            if re.match(r"^#+\s*1[\.\s]+Introduction", stripped, re.IGNORECASE):
                body_start = idx
                break
            # 纯英文论文可能用 "1. Introduction" 格式
            if re.match(r"^#+\s*1\.\s+Introduction", stripped, re.IGNORECASE):
                body_start = idx
                break

    # 摘要之后、正文第一章之前还有 ABSTRACT 段和英文目录，跳过
    real_body_start = body_start
    if body_start < n:
        for idx in range(body_start + 1, min(body_start + 300, n)):
            stripped = lines[idx].strip()
            # 找到第一章
            if re.match(r"^#+\s*第\s*1\s*章", stripped):
                real_body_start = idx
                break
            if re.match(r"^#+\s*(?:Chapter|CHAPTER)\s+1\b", stripped):
                real_body_start = idx
                break
            if re.match(r"^#+\s*1[\.\s]+Introduction", stripped, re.IGNORECASE):
                real_body_start = idx
                break
        else:
            real_body_start = body_start

    if real_body_start > 0:
        zones.append(_Zone(0, real_body_start, "cover_toc"))

    # 2. 文末噪音区域：参考文献/附录/致谢（从后往前，找最早的）
    end_start = n
    for idx in range(n - 1, -1, -1):
        stripped = lines[idx].strip()
        for keyword in _END_NOISE_SECTIONS:
            if stripped == f"# {keyword}" or stripped == f"## {keyword}":
                end_start = idx
                break

    if end_start < n:
        zones.append(_Zone(end_start, n, "end_noise"))

    # 4. 填充 body 区域
    covered = set()
    for z in zones:
        covered.update(range(z.start, z.end))

    body_regions: list[_Zone] = []
    body_start = None
    for idx in range(n):
        if idx in covered:
            if body_start is not None:
                body_regions.append(_Zone(body_start, idx, "body"))
                body_start = None
        else:
            if body_start is None:
                body_start = idx
    if body_start is not None:
        body_regions.append(_Zone(body_start, n, "body"))

    zones.extend(body_regions)
    zones.sort(key=lambda z: z.start)
    return zones


# ── 语义块提取 ──

def _extract_chunks(
    lines: list[str],
    zones: list[_Zone],
    paper_id: str,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    section_stack: list[tuple[int, str]] = []  # (level, title)

    for zone in zones:
        if zone.zone_type != "body":
            continue

        current_lines: list[str] = []
        current_page = 0

        def flush(chunk_idx: int):
            if not current_lines:
                return
            text = "\n".join(current_lines).strip()
            if not text:
                return
            section_title = " > ".join(t for _, t in section_stack) if section_stack else ""
            chunks.append(Chunk(
                chunk_id=f"{paper_id}_md_{chunk_idx:04d}",
                content=text,
                page=current_page,
                chunk_type=_detect_chunk_type(text),
                section_title=section_title,
                section_level=section_stack[-1][0] if section_stack else 0,
                has_image="true" if "![" in text else "false",
            ))
            current_lines.clear()

        chunk_idx = len(chunks)

        for idx in range(zone.start, zone.end):
            line = lines[idx]
            stripped = line.strip()

            # 空行：可能触发 flush
            if not stripped:
                continue

            # 页码标记（MinerU 可能不生成，但保留兼容）
            page_marker = re.match(r"<!--\s*page\s*(\d+)\s*-->", stripped)
            if page_marker:
                current_page = int(page_marker.group(1))
                continue

            # 标题行
            heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading:
                flush(chunk_idx)
                chunk_idx = len(chunks)
                level = len(heading.group(1))
                title = heading.group(2).strip()
                # 跳过噪音标题
                if _is_noise_title(title):
                    continue
                section_stack = [(l, t) for l, t in section_stack if l < level]
                section_stack.append((level, title))
                continue

            # 目录行（页码引用）
            if _TOC_LINE.match(stripped):
                continue

            # 短碎片行（封面残余、学校名等）
            if len(stripped) <= _SHORT_LINE_MAX and not re.match(r"^[\d.]+$", stripped):
                continue

            # 学校名/封面关键词
            if stripped in _SCHOOL_NAMES:
                continue
            if any(kw in stripped for kw in _COVER_KEYWORDS) and len(stripped) < 50:
                continue

            current_lines.append(stripped)

        flush(chunk_idx)

    return chunks


def _detect_chunk_type(text: str) -> str:
    if text.startswith("<table") or text.startswith("<TABLE"):
        return "table"
    if re.match(r"^\$[\s\S]+\$$", text):
        return "equation"
    if "![" in text:
        return "image"
    return "paragraph"


def _is_noise_title(title: str) -> bool:
    """判断标题是否是噪音（如碎片学校名、封面信息）"""
    if title in _SCHOOL_NAMES:
        return True
    if len(title) <= 2 and not re.match(r"^[\d.]+$", title):
        return True
    if title in ("CONTENTS",):
        return True
    return False


# ── 后处理过滤 ──

_FILTER_PATTERNS = (
    re.compile(r"学位论文评阅及答辩情况表.*", re.DOTALL),
    re.compile(r"<table>.*?</table>", re.DOTALL),  # 空问卷表格
)

_SPACED_ABBREVS = {
    "L L M": "LLM", "N L P": "NLP", "G P U": "GPU",
    "T P U": "TPU", "C P U": "CPU",
}


def _filter_noise(chunks: list[Chunk]) -> list[Chunk]:
    """后处理：过滤残余噪音"""
    result: list[Chunk] = []
    for chunk in chunks:
        text = chunk.content

        # 缩写修复
        for abbr, fix in _SPACED_ABBREVS.items():
            text = text.replace(abbr, fix)

        # 过滤只有页码引用的短块
        if len(text) < 10 and _TOC_LINE.match(text):
            continue

        # 过滤空表格块
        if text.startswith("<table") and "</td></tr></table>" in text:
            # 检查是否是空表格（只有表头）
            cells = re.findall(r"<td>([^<]*)</td>", text)
            if all(not c.strip() for c in cells[1:]):
                continue

        # 过滤答辩表等
        if "学位论文评阅" in text or "答辩委员会" in text:
            continue

        chunk.content = text
        result.append(chunk)
    return result
