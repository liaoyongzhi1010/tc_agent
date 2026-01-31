"""Runner worker process (Redis queue)."""
from __future__ import annotations

import asyncio
import json
import time

from app.infrastructure.logger import get_logger
from app.infrastructure.runner_queue import RunnerQueue
from app.tools.tee.optee_runner import _run_inline

logger = get_logger("tc_agent.runner_worker")


def main() -> None:
    queue = RunnerQueue()
    logger.info("Runner worker started")

    while True:
        job_id = queue.pop(timeout=5)
        if not job_id:
            continue

        job = queue.get(job_id)
        if not job:
            continue

        try:
            payload = json.loads(job.get("payload", "{}"))
        except Exception:
            queue.set_error(job_id, "任务解析失败")
            continue

        queue.set_status(job_id, "running")
        logger.info("Runner job start", job_id=job_id)

        try:
            result = asyncio.run(_run_inline(**payload))
            queue.set_result(job_id, result.model_dump())
            logger.info("Runner job done", job_id=job_id)
        except Exception as exc:
            logger.error("Runner job failed", job_id=job_id, error=str(exc))
            queue.set_error(job_id, str(exc))

        time.sleep(0.2)


if __name__ == "__main__":
    main()
