from __future__ import annotations

from app.agent_layer.session.editor_context_store import EditorContextStore


async def test_put_and_get():
    store = EditorContextStore()
    await store.put({"session_id": "s1", "data": "value"})
    result = await store.get("s1")
    assert result is not None
    assert result["data"] == "value"


async def test_get_none():
    store = EditorContextStore()
    assert await store.get("no_such") is None


async def test_delete():
    store = EditorContextStore()
    await store.put({"session_id": "s1", "data": "value"})
    await store.delete("s1")
    assert await store.get("s1") is None


async def test_delete_nonexistent():
    store = EditorContextStore()
    await store.delete("no_such")
    assert await store.get("no_such") is None


async def test_overwrite():
    store = EditorContextStore()
    await store.put({"session_id": "s1", "version": 1})
    await store.put({"session_id": "s1", "version": 2})
    result = await store.get("s1")
    assert result is not None
    assert result["version"] == 2
