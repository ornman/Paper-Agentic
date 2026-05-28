from __future__ import annotations


class ConversationWindowStore:
    def __init__(self, max_messages: int = 20) -> None:
        self._max_messages = max_messages
        self._store: dict[str, list[dict]] = {}

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
