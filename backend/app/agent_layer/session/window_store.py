from __future__ import annotations


class ConversationWindowStore:
    def __init__(self, max_messages: int = 20) -> None:
        self._max_messages = max_messages
        self._store: dict[str, list[dict]] = {}

    @classmethod
    def from_context_window(
        cls,
        context_window_tokens: int = 0,
        max_output_tokens: int = 0,
        avg_message_tokens: int = 0,
        system_prompt_tokens: int = 0,
    ) -> "ConversationWindowStore":
        from app.service_layer.config.settings import get_settings
        _s = get_settings()
        cwt = context_window_tokens or _s.context_window_tokens
        mot = max_output_tokens or _s.max_output_tokens
        amt = avg_message_tokens or _s.avg_message_tokens
        spt = system_prompt_tokens or _s.system_prompt_tokens
        available = cwt - mot - spt
        max_messages = max(4, available // amt)
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
