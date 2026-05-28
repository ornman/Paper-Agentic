from __future__ import annotations

from app.agent_layer.session.window_store import ConversationWindowStore


async def test_add_and_get():
    store = ConversationWindowStore(max_messages=10)
    await store.add_message("s1", {"role": "user", "content": "hello"})
    await store.add_message("s1", {"role": "assistant", "content": "hi"})
    messages = await store.get_messages("s1")
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


async def test_fifo_eviction():
    store = ConversationWindowStore(max_messages=3)
    for i in range(5):
        await store.add_message("s1", {"index": i})
    messages = await store.get_messages("s1")
    assert len(messages) == 3
    assert messages[0]["index"] == 2
    assert messages[2]["index"] == 4


async def test_session_isolation():
    store = ConversationWindowStore(max_messages=10)
    await store.add_message("s1", {"role": "user", "content": "a"})
    await store.add_message("s2", {"role": "user", "content": "b"})
    assert len(await store.get_messages("s1")) == 1
    assert len(await store.get_messages("s2")) == 1
    assert (await store.get_messages("s1"))[0]["content"] == "a"


async def test_clear():
    store = ConversationWindowStore(max_messages=10)
    await store.add_message("s1", {"role": "user", "content": "a"})
    await store.clear("s1")
    assert await store.get_messages("s1") == []


async def test_clear_nonexistent():
    store = ConversationWindowStore(max_messages=10)
    await store.clear("no_such_session")
    assert await store.get_messages("no_such_session") == []


async def test_get_empty():
    store = ConversationWindowStore(max_messages=10)
    assert await store.get_messages("s1") == []
