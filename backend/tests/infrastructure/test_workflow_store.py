"""工作流存储测试（内存 / Redis 可选）。"""
import os

import pytest

from app.infrastructure.workflow_store import MemoryWorkflowStore, RedisWorkflowStore
from app.schemas.models import Workflow, WorkflowStep


@pytest.mark.asyncio
async def test_memory_store_roundtrip():
    store = MemoryWorkflowStore()
    wf = Workflow(id="w1", task="t", steps=[WorkflowStep(id="1", description="d")])
    await store.set(wf)
    got = await store.get("w1")
    assert got and got.id == "w1"
    await store.delete("w1")
    assert await store.get("w1") is None


def _redis_ok(url: str) -> bool:
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_redis_store_roundtrip():
    url = os.getenv("TC_AGENT_REDIS_URL", "redis://localhost:6379/0")
    if not _redis_ok(url):
        pytest.skip("Redis 不可用，跳过")

    store = RedisWorkflowStore(url, ttl_seconds=60)
    wf = Workflow(id="w2", task="t", steps=[WorkflowStep(id="1", description="d")])
    await store.set(wf)
    got = await store.get("w2")
    assert got and got.id == "w2"
    await store.delete("w2")
