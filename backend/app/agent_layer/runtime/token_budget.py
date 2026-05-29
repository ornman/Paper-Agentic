"""Token 预算管理"""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    count = 0.0
    for ch in text:
        count += 1.5 if "一" <= ch <= "鿿" else 0.75
    return int(count)


class TokenBudget:
    _SENTINEL = -1

    def __init__(self, max_context: int = _SENTINEL, max_output: int = _SENTINEL) -> None:
        if max_context == self._SENTINEL or max_output == self._SENTINEL:
            from app.service_layer.config.settings import get_settings
            _s = get_settings()
            if max_context == self._SENTINEL:
                max_context = _s.context_window_tokens
            if max_output == self._SENTINEL:
                max_output = _s.max_output_tokens
        self._max_context = max_context
        self._max_output = max_output
        self._used = 0

    def can_fit(self, text: str) -> bool:
        return self._used + estimate_tokens(text) <= self._max_context

    def allocate(self, text: str) -> int:
        tokens = estimate_tokens(text)
        self._used += tokens
        return tokens

    @property
    def remaining(self) -> int:
        return max(0, self._max_context - self._used)

    @property
    def remaining_ratio(self) -> float:
        if self._max_context <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining / self._max_context))

    @property
    def max_output(self) -> int:
        return self._max_output
