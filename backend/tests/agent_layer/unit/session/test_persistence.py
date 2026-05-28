from __future__ import annotations

from app.agent_layer.session.persistence import SessionPersistence


async def test_save_and_get_messages():
    db = SessionPersistence()
    await db.save_message("s1", "user", "hello")
    await db.save_message("s1", "assistant", "hi")
    messages = await db.get_messages("s1")
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert messages[1]["role"] == "assistant"


async def test_save_and_get_summary():
    db = SessionPersistence()
    assert await db.get_summary("s1") is None
    await db.save_summary("s1", "这是一个摘要")
    assert await db.get_summary("s1") == "这是一个摘要"


async def test_get_messages_limit():
    db = SessionPersistence()
    for i in range(10):
        await db.save_message("s1", "user", f"msg_{i}")
    messages = await db.get_messages("s1", limit=3)
    assert len(messages) == 3
    assert messages[0]["content"] == "msg_7"
    assert messages[2]["content"] == "msg_9"


async def test_messages_with_optional_fields():
    db = SessionPersistence()
    await db.save_message("s1", "user", "hello", blocks_json='[{"type":"paragraph"}]', sources_json='[{"id":"src_1"}]')
    messages = await db.get_messages("s1")
    assert messages[0]["blocks_json"] is not None
    assert messages[0]["sources_json"] is not None


async def test_session_isolation():
    db = SessionPersistence()
    await db.save_message("s1", "user", "a")
    await db.save_message("s2", "user", "b")
    assert len(await db.get_messages("s1")) == 1
    assert len(await db.get_messages("s2")) == 1
    assert (await db.get_messages("s1"))[0]["content"] == "a"
