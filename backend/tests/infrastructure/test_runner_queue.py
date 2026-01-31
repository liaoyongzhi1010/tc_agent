"""Runner 队列测试（需要 Redis，若不可用则跳过）。"""
import os

import pytest

from app.infrastructure.runner_queue import RunnerQueue


def _redis_ok(url: str) -> bool:
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        return True
    except Exception:
        return False


def test_runner_queue_enqueue_and_pop():
    url = os.getenv("TC_AGENT_REDIS_URL", "redis://localhost:6379/0")
    if not _redis_ok(url):
        pytest.skip("Redis 不可用，跳过")

    queue = RunnerQueue()
    job_id = queue.enqueue({"hello": "world"})
    assert job_id

    popped = queue.pop(timeout=1)
    assert popped == job_id
