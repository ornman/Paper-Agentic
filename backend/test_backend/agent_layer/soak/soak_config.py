from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SoakConfig:
    # 运行参数
    duration_seconds: int = 7200          # 默认 2 小时
    request_interval_seconds: float = 30  # 每轮间隔
    concurrent_sessions: int = 1          # 并发 session 数

    # 故障注入
    fault_injection_rate: float = 0.0     # 0.0 ~ 1.0，0 = 不注入
    fault_types: list[str] = field(default_factory=lambda: [
        "llm_timeout", "llm_error", "llm_empty", "retrieval_fail"
    ])

    # 告警阈值
    max_response_time_seconds: float = 30.0
    max_memory_mb: float = 500.0
    min_success_rate: float = 0.95

    # 输出
    report_dir: str = "tests/agent_layer/_artifacts/soak_reports"
    log_file: str | None = None


# 预设 prompt 模板（50 个）
SIMPLE_QA_PROMPTS = [
    "什么是机器学习？",
    "解释一下梯度下降的原理",
    "深度学习和传统机器学习有什么区别？",
    "什么是过拟合？如何避免？",
    "解释一下反向传播算法",
    "什么是卷积神经网络？",
    "Transformer 架构的核心思想是什么？",
    "什么是注意力机制？",
    "解释一下 BERT 模型",
    "什么是 GPT？它和 BERT 有什么区别？",
]

ACADEMIC_PROMPTS = [
    "这篇论文的主要贡献是什么？",
    "帮我总结一下相关工作部分",
    "这个方法的创新点在哪里？",
    "实验结果说明了什么？",
    "这篇论文有什么局限性？",
    "帮我改写这段摘要，使其更学术化",
    "这段文字的论证逻辑是否严密？",
    "这个实验设计是否合理？",
    "对比一下这两篇论文的方法",
    "帮我找一下这个概念的定义",
    "这段引用是否正确支持了论点？",
    "这个公式的推导过程是什么？",
    "论文中的这个图表说明了什么？",
    "帮我检查这段文字的学术规范性",
    "这个方法在实际应用中有什么限制？",
]

EDGE_CASE_PROMPTS = [
    "",                          # 空 prompt
    "a",                         # 极短
    "请" * 500,                  # 超长（2000 字）
    "!@#$%^&*()",               # 纯特殊字符
    "Hello 你好 こんにちは",      # 多语言混合
    "\n\n\n",                    # 纯换行
    "   ",                       # 纯空格
    "这是一个测试" * 200,        # 重复文本
    "What is RAG? 什么是检索增强生成？Explain in detail.",  # 中英混合长句
    "1. 第一点\n2. 第二点\n3. 第三点\n",  # 结构化输入
]

ALL_PROMPTS = SIMPLE_QA_PROMPTS + ACADEMIC_PROMPTS + EDGE_CASE_PROMPTS


def get_soak_config(**overrides) -> SoakConfig:
    """获取浸泡测试配置，支持覆盖参数"""
    return SoakConfig(**overrides)
