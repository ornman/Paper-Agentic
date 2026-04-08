# Query 改写服务
# 根据用户输入场景（4种组合）生成适合检索的查询文本
#
# 设计来源：D042 决策
# 场景1：仅 prompt → 直接用 prompt 改写
# 场景2：仅已写内容 → 推断续写意图，生成检索 query
# 场景3：已写 + 圈选 → 组合（已写 30% + 圈选 70%）
# 场景4：已写 + 圈选 + prompt → 组合（已写 20% + 圈选 30% + prompt 50%）
#
# MVP 实现：用 LLM 做改写（简单有效），不做规则改写

from typing import Optional
from app.clients.llm_client import LLMClient
from app.models.query import QueryContext


# ============================================================
# 改写 Prompt 模板
# ============================================================

# 场景 1：仅有用户 prompt
_REWRITE_PROMPT_ONLY = """\
你是一个学术检索助手。用户提出了一个问题，请将其改写为 1-3 个适合在学术文献库中检索的查询语句。

要求：
- 提取核心概念和关键词
- 去除口语化表达，转为学术用语
- 如果问题涉及多个方面，拆分为多个独立的检索查询
- 每个查询独占一行，不要编号

用户问题：{query}

改写后的检索查询："""

# 场景 2：仅有已写内容（推断续写意图）
_REWRITE_WRITTEN_ONLY = """\
你是一个学术检索助手。用户正在写论文，以下是已写的内容。请分析已写内容，推断用户接下来可能需要什么参考资料，生成 1-3 个检索查询。

要求：
- 分析已写内容的主题和论述方向
- 推断下一步可能需要的论据、数据或理论支撑
- 生成适合在学术文献库中检索的查询
- 每个查询独占一行，不要编号

已写内容（最后 500 字）：
{written_content}

推断出的检索查询："""

# 场景 3：已写 + 圈选（圈选为重点）
_REWRITE_WRITTEN_SELECTED = """\
你是一个学术检索助手。用户正在写论文，圈选了一段文本想要深入了解。请根据圈选文本和已写内容，生成 1-3 个检索查询。

要求：
- 以圈选文本为重点（70%权重），已写内容提供上下文（30%权重）
- 提取圈选文本中的核心概念
- 结合上下文推断用户的检索意图
- 每个查询独占一行，不要编号

已写内容（摘要）：
{written_content}

圈选文本：
{selected_text}

检索查询："""

# 场景 4：已写 + 圈选 + prompt（最完整的输入）
_REWRITE_FULL = """\
你是一个学术检索助手。用户正在写论文，圈选了一段文本，并提出了具体问题。请综合所有信息，生成 1-3 个检索查询。

要求：
- 用户提问为最高优先级（50%权重）
- 圈选文本次之（30%权重）
- 已写内容提供背景（20%权重）
- 生成精准的学术检索查询
- 每个查询独占一行，不要编号

已写内容（摘要）：
{written_content}

圈选文本：
{selected_text}

用户提问：
{query}

检索查询："""


class QueryRewriteService:
    """Query 改写服务"""

    def __init__(self):
        self._llm = LLMClient()

    async def rewrite(
        self,
        query: str,
        context: Optional[QueryContext] = None,
    ) -> list[str]:
        """
        根据输入场景改写查询

        Args:
            query: 用户原始查询
            context: 上下文（已写内容、圈选文本、prompt）

        Returns:
            改写后的查询列表（1-3 个）
        """
        # 判断场景，选择模板
        prompt = self._select_prompt(query, context)

        # 调用 LLM 改写
        messages = [
            {"role": "system", "content": "你是学术检索查询改写专家，输出简洁的检索语句。"},
            {"role": "user", "content": prompt},
        ]

        try:
            raw_output = await self._llm.chat(messages)
            queries = self._parse_queries(raw_output, query)
            return queries
        except Exception as e:
            # 改写失败时降级：直接用原始查询
            print(f"Query 改写失败，降级使用原始查询: {e}")
            return [query]

    def _select_prompt(
        self,
        query: str,
        context: Optional[QueryContext],
    ) -> str:
        """
        根据输入组合选择改写模板

        判断逻辑：
        - 有 context.prompt → 视为用户明确提问，替代 query
        - 有 context.written_content → 提供已写上下文
        - 有 context.selected_text → 提供圈选重点
        """
        # 确定实际的查询文本
        # 如果 context 里有 prompt，优先用 prompt 作为查询意图
        actual_query = query
        if context and context.prompt:
            actual_query = context.prompt

        has_written = bool(context and context.written_content)
        has_selected = bool(context and context.selected_text)

        if has_written and has_selected:
            # 场景 3 或 4（取决于是否有额外 prompt）
            written_tail = self._truncate(context.written_content, 500)
            selected = self._truncate(context.selected_text, 300)

            if context.prompt:
                # 场景 4：三者都有
                return _REWRITE_FULL.format(
                    written_content=written_tail,
                    selected_text=selected,
                    query=actual_query,
                )
            else:
                # 场景 3：已写 + 圈选
                return _REWRITE_WRITTEN_SELECTED.format(
                    written_content=written_tail,
                    selected_text=selected,
                )

        if has_written:
            # 场景 2：仅已写内容
            written_tail = self._truncate(context.written_content, 500)
            return _REWRITE_WRITTEN_ONLY.format(written_content=written_tail)

        # 场景 1：仅有 prompt / query
        return _REWRITE_PROMPT_ONLY.format(query=actual_query)

    def _parse_queries(self, raw_output: str, fallback: str) -> list[str]:
        """
        解析 LLM 输出为查询列表

        规则：
        - 按行分割
        - 去掉空行、编号前缀（1. 2. 3. 等）
        - 去掉引号包裹
        - 最多保留 3 个
        - 如果解析结果为空，回退到原始查询
        """
        lines = raw_output.strip().split("\n")
        queries = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 去掉常见的编号前缀
            import re
            line = re.sub(r"^[\d]+[.、)）]\s*", "", line)
            line = re.sub(r"^[-•*]\s*", "", line)

            # 去掉引号包裹
            if (line.startswith('"') and line.endswith('"')) or \
               (line.startswith("'") and line.endswith("'")):
                line = line[1:-1]
            if (line.startswith('"') and line.endswith('"')) or \
               (line.startswith(''') and line.endswith(''')):
                line = line[1:-1]

            line = line.strip()
            if line and len(line) > 3:  # 过滤太短的结果
                queries.append(line)

        # 最多 3 个
        queries = queries[:3]

        # 兜底
        if not queries:
            queries = [fallback]

        return queries

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """截断文本，保留末尾（最新写的内容更重要）"""
        if len(text) <= max_len:
            return text
        return "..." + text[-max_len:]
