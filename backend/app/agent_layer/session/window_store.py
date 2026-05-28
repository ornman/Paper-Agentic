from __future__ import annotations


class ConversationWindowStore:
    def __init__(self, max_messages: int = 20) -> None:
        self._max_messages = max_messages
        self._store: dict[str, list[dict]] = {}

    @classmethod
    def from_context_window(
        cls,
        context_window_tokens: int = 32000,
        max_output_tokens: int = 4096,
        avg_message_tokens: int = 500,
        system_prompt_tokens: int = 2000,
    ) -> "ConversationWindowStore":
        available = context_window_tokens - max_output_tokens - system_prompt_tokens
        max_messages = max(4, available // avg_message_tokens)
        return cls(max_messages=max_messages)

    async def get_messages(self, session_id: str) -> list[dict]:
        return list(self._store.get(session_id, []))

    async def add_message(self, session_id: str, message: dict) -> None:
        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append(message)
        if len(self._store[session_id]) > self._max_messages:
            self._store[session_id] = self._store[session_id][-self._max_messages:]

    async def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
