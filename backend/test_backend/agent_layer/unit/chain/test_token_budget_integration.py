"""TokenBudget 在真实场景下的行为集成测试"""

from __future__ import annotations

import pytest

from app.agent_layer.runtime.token_budget import TokenBudget, estimate_tokens


# ── estimate_tokens 基础 ─────────────────────────────────────────────


async def test_estimate_chinese_chars():
    """中文字符按 1.5 token 估算"""
    tokens = estimate_tokens("你好世界")
    # 4 个中文字符 × 1.5 = 6
    assert tokens == 6


async def test_estimate_ascii_chars():
    """ASCII 字符按 0.75 token 估算"""
    tokens = estimate_tokens("hello")
    # 5 个 ASCII 字符 × 0.75 = 3.75 → int(3.75) = 3
    assert tokens == 3


async def test_estimate_mixed_text():
    """混合文本正确估算"""
    tokens = estimate_tokens("hello你好")
    # 5 × 0.75 + 2 × 1.5 = 3.75 + 3 = 6.75 → int = 6
    assert tokens == 6


async def test_estimate_empty_string():
    """空字符串 → 0"""
    assert estimate_tokens("") == 0


# ── TokenBudget 基础操作 ─────────────────────────────────────────────


async def test_budget_can_fit_small_text():
    """小文本能放入预算"""
    budget = TokenBudget(max_context=30000)
    assert budget.can_fit("短文本") is True


async def test_budget_cannot_fit_huge_text():
    """超大文本无法放入预算"""
    budget = TokenBudget(max_context=30000)
    huge = "你" * 30000  # 30000 × 1.5 = 45000 tokens > 30000
    assert budget.can_fit(huge) is False


async def test_budget_allocate_reduces_remaining():
    """分配后剩余减少"""
    budget = TokenBudget(max_context=30000)
    initial_remaining = budget.remaining
    budget.allocate("测试文本")
    assert budget.remaining < initial_remaining


async def test_budget_remaining_non_negative():
    """剩余永远 >= 0"""
    budget = TokenBudget(max_context=10)
    budget.allocate("你" * 100)
    assert budget.remaining >= 0


async def test_budget_remaining_ratio():
    """remaining_ratio 正确反映使用比例"""
    budget = TokenBudget(max_context=30000)
    assert budget.remaining_ratio == 1.0
    budget.allocate("你" * 10000)  # 15000 tokens
    assert 0.4 < budget.remaining_ratio < 0.6


# ── 真实场景模拟 ─────────────────────────────────────────────────────


async def test_budget_with_realistic_retrieval():
    """模拟真实检索结果的 token 预算管理"""
    budget = TokenBudget(max_context=30000)
    results = [{"content": "这是一段" * 100} for _ in range(100)]  # ~400 tokens each
    kept = 0
    for doc in results:
        content = doc["content"]
        if budget.can_fit(content):
            budget.allocate(content)
            kept += 1
        else:
            break
    assert kept < 100  # 应该被截断
    assert kept > 0  # 至少能放一些
    assert budget.remaining >= 0


async def test_budget_single_huge_doc():
    """单条超大文档被跳过"""
    budget = TokenBudget(max_context=30000)
    huge = "你" * 30000  # 45000 tokens > 30000
    assert budget.can_fit(huge) is False


async def test_budget_multiple_small_docs():
    """多条小文档全部保留"""
    budget = TokenBudget(max_context=30000)
    small = "短文本" * 10  # ~30 tokens
    for _ in range(50):
        assert budget.can_fit(small)
        budget.allocate(small)
    assert budget.remaining > 0


async def test_budget_fills_up_exactly():
    """预算填满后无法再放入"""
    budget = TokenBudget(max_context=100)
    # 中文字符 "你" = 1.5 tokens, 放 66 个 = 99 tokens, 再放 1 个 = 100.5 > 100
    text = "你" * 67  # 67 × 1.5 = 100.5 → int(100.5) = 100
    assert budget.can_fit(text) is True
    budget.allocate(text)
    assert budget.remaining == 0
    # 再放一个就超了
    assert budget.can_fit("你") is False


async def test_budget_allocate_returns_tokens():
    """allocate 返回消耗的 token 数"""
    budget = TokenBudget(max_context=30000)
    tokens = budget.allocate("你好")
    assert tokens == estimate_tokens("你好")
    assert tokens > 0
