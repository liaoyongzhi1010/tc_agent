"""Redis-backed runner queue."""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Optional

import redis  # type: ignore

from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.runner_queue")


class RunnerQueue:
    def __init__(self) -> None:
        url = os.getenv("TC_AGENT_REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.Redis.from_url(url, decode_responses=True)
        self._queue_key = os.getenv("TC_AGENT_RUNNER_QUEUE_KEY", "tc_agent:queue:runner")
        self._ttl = int(os.getenv("TC_AGENT_RUNNER_TTL", "86400"))

    def enqueue(self, payload: dict) -> str:
        job_id = uuid.uuid4().hex
        key = self._job_key(job_id)
        now = int(time.time())
        self._redis.hset(
            key,
            mapping={
                "id": job_id,
                "status": "queued",
                "created_at": now,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )
        if self._ttl > 0:
            self._redis.expire(key, self._ttl)
        self._redis.lpush(self._queue_key, job_id)
        return job_id

    def pop(self, timeout: int = 5) -> Optional[str]:
        item = self._redis.brpop(self._queue_key, timeout=timeout)
        if not item:
            return None
        return item[1]

    def get(self, job_id: str) -> Optional[dict]:
        key = self._job_key(job_id)
        data = self._redis.hgetall(key)
        return data or None

    def set_status(self, job_id: str, status: str) -> None:
        key = self._job_key(job_id)
        self._redis.hset(key, "status", status)

    def set_result(self, job_id: str, result: dict) -> None:
        key = self._job_key(job_id)
        payload = json.dumps(result, ensure_ascii=False)
        self._redis.hset(key, mapping={"status": "done", "result": payload})

    def set_error(self, job_id: str, error: str) -> None:
        key = self._job_key(job_id)
        self._redis.hset(key, mapping={"status": "failed", "error": error})

    def wait(self, job_id: str, timeout: int = 1200, poll: float = 1.0) -> Optional[dict]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self.get(job_id)
            if not data:
                return None
            status = data.get("status")
            if status in ("done", "failed"):
                return data
            time.sleep(poll)
        return None

    def _job_key(self, job_id: str) -> str:
        return f"tc_agent:job:{job_id}"
