"""EditorContextStore 单元测试（含冻结副本 + 轮询）"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.agent_layer.session.editor_context_store import EditorContextStore


# ── 基础 CRUD ─────────────────────────────────────────────────────


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


# ── 冻结副本 ──────────────────────────────────────────────────────


async def test_freeze_returns_deep_copy():
    """freeze 返回深拷贝，修改不影响原数据"""
    store = EditorContextStore()
    await store.put({"session_id": "s1", "draft": "原始内容"})

    frozen = store.freeze("s1", "req-1")
    assert frozen is not None
    assert frozen["draft"] == "原始内容"

    # 修改 frozen 不影响 live
    frozen["draft"] = "已修改"
    live = await store.get("s1")
    assert live["draft"] == "原始内容"


async def test_freeze_none_when_empty():
    """session 不存在时 freeze 返回 None"""
    store = EditorContextStore()
    assert store.freeze("no_such", "req-1") is None


async def test_get_frozen_returns_snapshot():
    """get_frozen 返回冻结时刻的快照"""
    store = EditorContextStore()
    await store.put({"session_id": "s1", "draft": "v1"})

    store.freeze("s1", "req-1")

    # live 更新
    await store.put({"session_id": "s1", "draft": "v2"})

    # frozen 仍是 v1
    frozen = store.get_frozen("req-1")
    assert frozen is not None
    assert frozen["draft"] == "v1"

    # live 是 v2
    live = await store.get("s1")
    assert live["draft"] == "v2"


async def test_get_frozen_expired():
    """过期的冻结副本返回 None"""
    store = EditorContextStore()
    await store.put({"session_id": "s1", "draft": "v1"})

    store.freeze("s1", "req-1")
    # 手动过期
    store._frozen["req-1"] = (store._frozen["req-1"][0], time.monotonic() - 600)

    assert store.get_frozen("req-1") is None


async def test_get_frozen_nonexistent():
    """不存在的 request_id 返回 None"""
    store = EditorContextStore()
    assert store.get_frozen("no_such") is None


async def test_multiple_frozen_isolated():
    """不同 request_id 的冻结副本互相隔离"""
    store = EditorContextStore()
    await store.put({"session_id": "s1", "draft": "v1"})

    store.freeze("s1", "req-1")
    await store.put({"session_id": "s1", "draft": "v2" })
    store.freeze("s1", "req-2")

    f1 = store.get_frozen("req-1")
    f2 = store.get_frozen("req-2")
    assert f1["draft"] == "v1"
    assert f2["draft"] == "v2"


async def test_cleanup_frozen():
    """cleanup_frozen 清理过期副本"""
    store = EditorContextStore()
    await store.put({"session_id": "s1", "draft": "v1"})

    store.freeze("s1", "req-1")
    store.freeze("s1", "req-2")

    # 手动过期 req-1
    store._frozen["req-1"] = (store._frozen["req-1"][0], time.monotonic() - 600)

    cleaned = store.cleanup_frozen(max_age=300)
    assert cleaned == 1
    assert store.get_frozen("req-1") is None
    assert store.get_frozen("req-2") is not None


# ── WPS 轮询 ──────────────────────────────────────────────────────


async def test_start_and_stop_polling():
    """轮询可以启动和停止"""
    store = EditorContextStore()
    poll_count = 0

    async def mock_poll():
        nonlocal poll_count
        poll_count += 1
        return {"draft": f"content-{poll_count}"}

    store.start_polling(mock_poll, "s1", interval=0.05)
    await asyncio.sleep(0.2)

    store.stop_polling()
    assert poll_count >= 2

    # 停止后数据应该已写入
    result = await store.get("s1")
    assert result is not None
    assert "content-" in result["draft"]


async def test_polling_error_does_not_crash():
    """轮询函数抛异常时不影响后续轮询"""
    store = EditorContextStore()
    call_count = 0

    async def flaky_poll():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("WPS 连接断开")
        return {"draft": "recovered"}

    store.start_polling(flaky_poll, "s1", interval=0.05)
    await asyncio.sleep(0.2)
    store.stop_polling()

    # 应该恢复并写入数据
    result = await store.get("s1")
    assert result is not None


async def test_polling_no_double_start():
    """重复启动轮询不会创建多个任务"""
    store = EditorContextStore()

    async def noop():
        return None

    store.start_polling(noop, "s1", interval=0.05)
    task1 = store._poll_task

    store.start_polling(noop, "s1", interval=0.05)
    task2 = store._poll_task

    assert task1 is task2
    store.stop_polling()
