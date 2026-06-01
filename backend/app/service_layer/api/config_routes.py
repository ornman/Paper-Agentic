"""配置持久化 API — 读写 .env 文件（重启生效）"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter(tags=["config"])

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
_env_lock = asyncio.Lock()


def _mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return "****" + value[-4:]


class ConfigUpdateRequest(BaseModel):
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    mineru_api_key: str | None = None
    mineru_base_url: str | None = None
    mineru_poll_interval: str | None = None
    mineru_timeout: str | None = None

    @field_validator(
        "llm_api_key", "llm_base_url", "llm_model",
        "embedding_api_key", "embedding_base_url",
        "mineru_api_key", "mineru_base_url",
        "mineru_poll_interval", "mineru_timeout",
        mode="before",
    )
    @classmethod
    def strip_and_reject_newlines(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if "\n" in v or "\r" in v:
            raise ValueError("Value must not contain newlines")
        return v


def _parse_env_lines(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def _build_env_text(original: str, updates: dict[str, str]) -> str:
    lines = original.splitlines()
    updated_keys: set[str] = set()
    result_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            result_lines.append(line)
            continue

        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", stripped)
        if match and match.group(1) in updates:
            result_lines.append(f"{match.group(1)}={updates[match.group(1)]}")
            updated_keys.add(match.group(1))
        else:
            result_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            result_lines.append(f"{key}={value}")

    return "\n".join(result_lines) + "\n"


_FIELD_TO_ENV = {
    "llm_api_key": "LLM_API_KEY",
    "llm_base_url": "LLM_BASE_URL",
    "llm_model": "LLM_MODEL",
    "embedding_api_key": "EMBEDDING_API_KEY",
    "embedding_base_url": "EMBEDDING_BASE_URL",
    "mineru_api_key": "MINERU_API_KEY",
    "mineru_base_url": "MINERU_BASE_URL",
    "mineru_poll_interval": "MINERU_POLL_INTERVAL",
    "mineru_timeout": "MINERU_TIMEOUT",
}

_MASK_FIELDS = {
    "llm_api_key": "LLM_API_KEY",
    "embedding_api_key": "EMBEDDING_API_KEY",
    "mineru_api_key": "MINERU_API_KEY",
}

_NON_MASK_FIELDS = {
    "llm_base_url": "LLM_BASE_URL",
    "llm_model": "LLM_MODEL",
    "embedding_base_url": "EMBEDDING_BASE_URL",
    "mineru_base_url": "MINERU_BASE_URL",
    "mineru_poll_interval": "MINERU_POLL_INTERVAL",
    "mineru_timeout": "MINERU_TIMEOUT",
}


@router.get("/config/env")
async def get_config():
    if not _ENV_PATH.exists():
        return {"data": {}, "configured": {"llm": False, "embedding": False, "mineru": False}}

    env_text = _ENV_PATH.read_text(encoding="utf-8")
    env_map = _parse_env_lines(env_text)

    data: dict[str, str] = {}
    for field, env_key in _MASK_FIELDS.items():
        data[field] = _mask_key(env_map.get(env_key, ""))
    for field, env_key in _NON_MASK_FIELDS.items():
        data[field] = env_map.get(env_key, "")

    configured = {
        "llm": bool(env_map.get("LLM_API_KEY") and env_map.get("LLM_BASE_URL")),
        "embedding": bool(env_map.get("EMBEDDING_API_KEY") and env_map.get("EMBEDDING_BASE_URL")),
        "mineru": bool(env_map.get("MINERU_API_KEY")),
    }

    return {"data": data, "configured": configured}


@router.post("/config/env")
async def update_config(req: ConfigUpdateRequest):
    if not _ENV_PATH.exists():
        _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        _ENV_PATH.write_text("", encoding="utf-8")

    updates: dict[str, str] = {}
    for field, env_key in _FIELD_TO_ENV.items():
        value = getattr(req, field, None)
        if value is not None:
            updates[env_key] = value

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    async with _env_lock:
        env_text = _ENV_PATH.read_text(encoding="utf-8")
        new_text = _build_env_text(env_text, updates)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(_ENV_PATH.parent), suffix=".env.tmp", prefix=".env_"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(new_text)
            os.replace(tmp_path, str(_ENV_PATH))
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    return {"message": "Configuration saved", "restart_required": True}
