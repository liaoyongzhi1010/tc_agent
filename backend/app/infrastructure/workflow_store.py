"""Workflow storage with optional Redis backend."""
from __future__ import annotations

import os
from typing import Optional, Protocol

from app.infrastructure.logger import get_logger
from app.schemas.models import Workflow

logger = get_logger("tc_agent.workflow_store")


class WorkflowStore(Protocol):
    async def get(self, workflow_id: str) -> Optional[Workflow]:
        ...

    async def set(self, workflow: Workflow) -> None:
        ...

    async def delete(self, workflow_id: str) -> None:
        ...


class MemoryWorkflowStore:
    def __init__(self) -> None:
        self._data: dict[str, Workflow] = {}

    async def get(self, workflow_id: str) -> Optional[Workflow]:
        return self._data.get(workflow_id)

    async def set(self, workflow: Workflow) -> None:
        self._data[workflow.id] = workflow

    async def delete(self, workflow_id: str) -> None:
        self._data.pop(workflow_id, None)


class RedisWorkflowStore:
    def __init__(self, url: str, ttl_seconds: int) -> None:
        import redis  # type: ignore

        self._redis = redis.Redis.from_url(url, decode_responses=True)
        self._ttl_seconds = ttl_seconds

    def _key(self, workflow_id: str) -> str:
        return f"tc_agent:workflow:{workflow_id}"

    async def get(self, workflow_id: str) -> Optional[Workflow]:
        data = self._redis.get(self._key(workflow_id))
        if not data:
            return None
        return Workflow.model_validate_json(data)

    async def set(self, workflow: Workflow) -> None:
        payload = workflow.model_dump_json()
        if self._ttl_seconds > 0:
            self._redis.setex(self._key(workflow.id), self._ttl_seconds, payload)
        else:
            self._redis.set(self._key(workflow.id), payload)

    async def delete(self, workflow_id: str) -> None:
        self._redis.delete(self._key(workflow_id))


_store: WorkflowStore | None = None


def get_workflow_store() -> WorkflowStore:
    global _store
    if _store is not None:
        return _store

    backend = os.getenv("TC_AGENT_WORKFLOW_STORE", "memory").strip().lower()
    if backend == "redis":
        try:
            import redis  # type: ignore  # noqa: F401
        except Exception:
            logger.warning("Redis未安装，回退到内存存储")
            _store = MemoryWorkflowStore()
            return _store

        url = os.getenv("TC_AGENT_REDIS_URL", "redis://localhost:6379/0")
        ttl = int(os.getenv("TC_AGENT_WORKFLOW_TTL", "86400"))
        _store = RedisWorkflowStore(url, ttl)
        logger.info("Workflow store: redis", url=url, ttl=ttl)
        return _store

    _store = MemoryWorkflowStore()
    logger.info("Workflow store: memory")
    return _store
