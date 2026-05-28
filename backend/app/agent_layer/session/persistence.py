from __future__ import annotations


class SessionPersistence:
    def __init__(self) -> None:
        self._messages: dict[str, list[dict]] = {}
        self._summaries: dict[str, str] = {}

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        blocks_json: str | None = None,
        sources_json: str | None = None,
    ) -> None:
        if session_id not in self._messages:
            self._messages[session_id] = []
        self._messages[session_id].append(
            {
                "role": role,
                "content": content,
                "blocks_json": blocks_json,
                "sources_json": sources_json,
            }
        )

    async def get_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        messages = self._messages.get(session_id, [])
        return messages[-limit:]

    async def save_summary(self, session_id: str, summary: str) -> None:
        self._summaries[session_id] = summary

    async def get_summary(self, session_id: str) -> str | None:
        return self._summaries.get(session_id)
