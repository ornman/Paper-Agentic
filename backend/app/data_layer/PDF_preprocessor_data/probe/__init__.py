"""PDF 探针模块

对 PDF 做轻量特征检测，输出特征类型。
不做路由决策，只输出检测结果。
"""

from .pdf_probe import ProbeResult, probe_pdf

__all__ = ["probe_pdf", "ProbeResult"]
