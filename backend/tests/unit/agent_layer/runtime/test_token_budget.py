"""TokenBudget 测试"""

from __future__ import annotations

import pytest

from app.agent_layer.runtime.token_budget import TokenBudget, estimate_tokens


class TestEstimateTokens:
    def test_chinese_text(self):
        result = estimate_tokens("你好世界")
        assert result == 6

    def test_english_text(self):
        result = estimate_tokens("hello")
        assert result == 3

    def test_mixed_text(self):
        result = estimate_tokens("hello你好")
        assert result == 6

    def test_empty_text(self):
        assert estimate_tokens("") == 0

    def test_long_chinese(self):
        text = "这" * 1000
        assert estimate_tokens(text) == 1500

    def test_long_english(self):
        text = "a" * 1000
        assert estimate_tokens(text) == 750


class TestTokenBudget:
    def test_allocate_consumes_budget(self):
        budget = TokenBudget(max_context=100)
        used = budget.allocate("hello")
        assert used == 3
        assert budget.remaining == 97

    def test_can_fit_within_limit(self):
        budget = TokenBudget(max_context=100)
        assert budget.can_fit("hello") is True

    def test_can_fit_exceeds_limit(self):
        budget = TokenBudget(max_context=5)
        assert budget.can_fit("hello world") is False

    def test_remaining_ratio_full(self):
        budget = TokenBudget(max_context=100)
        assert budget.remaining_ratio == 1.0

    def test_remaining_ratio_partial(self):
        budget = TokenBudget(max_context=100)
        budget.allocate("hello")
        assert budget.remaining_ratio == pytest.approx(0.97, abs=0.01)

    def test_remaining_ratio_zero(self):
        budget = TokenBudget(max_context=0)
        assert budget.remaining_ratio == 0.0

    def test_multiple_allocate_accumulates(self):
        budget = TokenBudget(max_context=100)
        budget.allocate("hello")
        budget.allocate("world")
        assert budget.remaining == 94

    def test_allocate_returns_token_count(self):
        budget = TokenBudget(max_context=1000)
        assert budget.allocate("你好") == 3
        assert budget.allocate("hello") == 3

    def test_max_output_property(self):
        budget = TokenBudget(max_context=100, max_output=50)
        assert budget.max_output == 50

    def test_can_fit_after_budget_exhausted(self):
        budget = TokenBudget(max_context=5)
        budget.allocate("hello")
        assert budget.can_fit("hello") is False
