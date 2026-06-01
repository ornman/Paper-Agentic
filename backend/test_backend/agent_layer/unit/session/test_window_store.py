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


class TestFromContextWindow:
    def test_returns_conversation_window_store(self):
        store = ConversationWindowStore.from_context_window()
        assert isinstance(store, ConversationWindowStore)

    def test_minimum_messages_floor(self):
        """context_window 极小时，max_messages 不低于 4"""
        store = ConversationWindowStore.from_context_window(
            context_window_tokens=1000,
            max_output_tokens=2048,
        )
        assert store._max_messages >= 4

    def test_larger_context_yields_more_messages(self):
        """context_window 越大，窗口越大"""
        small = ConversationWindowStore.from_context_window(context_window_tokens=16000)
        large = ConversationWindowStore.from_context_window(context_window_tokens=128000)
        assert large._max_messages > small._max_messages

    def test_larger_output_reservation_yields_fewer_messages(self):
        """预留输出 token 越多，窗口越小"""
        low = ConversationWindowStore.from_context_window(max_output_tokens=2048)
        high = ConversationWindowStore.from_context_window(max_output_tokens=32000)
        assert low._max_messages > high._max_messages

    def test_formula_uses_avg_message_tokens(self):
        """avg_message_tokens 越大，窗口越小"""
        fine = ConversationWindowStore.from_context_window(avg_message_tokens=200)
        coarse = ConversationWindowStore.from_context_window(avg_message_tokens=1000)
        assert fine._max_messages > coarse._max_messages

    def test_formula_matches_manual_calculation(self):
        """验证公式: max(4, (ctx - out - sys) / avg)"""
        ctx, out, avg, sys = 64000, 4096, 500, 2000
        store = ConversationWindowStore.from_context_window(
            context_window_tokens=ctx,
            max_output_tokens=out,
            avg_message_tokens=avg,
            system_prompt_tokens=sys,
        )
        expected = max(4, (ctx - out - sys) // avg)
        assert store._max_messages == expected
