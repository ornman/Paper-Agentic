"""Markdown 清洗模块

对 transformation 产出的 markdown 做格式清洗和规范化。
语言分离架构：common.py（通用引擎） + zh_rules.py（中文） + en_rules.py（英文）。
"""

from .common import CleaningResult, LineRule, RegexRule
from .markdown_cleaner import clean_markdown, clean_mineru_output
from . import zh_rules, en_rules

__all__ = [
    "CleaningResult",
    "LineRule",
    "RegexRule",
    "clean_markdown",
    "clean_mineru_output",
    "zh_rules",
    "en_rules",
]
