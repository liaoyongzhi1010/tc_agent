"""optee_runner 工具测试（队列/内联分支）。"""
import json

import pytest

from app.schemas.models import ToolResult
from app.tools.tee import optee_runner as runner_module
from app.tools.tee.optee_runner import OpteeRunnerTool


class DummyQueue:
    def enqueue(self, payload: dict) -> str:
        return "job-1"

    def wait(self, job_id: str, timeout: int = 1200, poll: float = 1.0):
        return {
            "status": "done",
            "result": json.dumps(
                {"success": True, "data": {"log": "ok", "exit_code": 0}},
                ensure_ascii=False,
            ),
        }


@pytest.mark.asyncio
async def test_optee_runner_redis_queue(monkeypatch):
    monkeypatch.setattr(runner_module, "RUNNER_BACKEND", "redis")
    monkeypatch.setattr(runner_module, "RunnerQueue", DummyQueue)

    tool = OpteeRunnerTool()
    res = await tool.execute(
        workspace_id="ws",
        ta_dir="demo_ta",
        ca_dir="demo_ca",
        mode="full",
    )
    assert res.success
    assert res.data["exit_code"] == 0


@pytest.mark.asyncio
async def test_optee_runner_inline(monkeypatch):
    async def _fake_inline(**kwargs):
        return ToolResult(success=True, data={"log": "ok", "exit_code": 0})

    monkeypatch.setattr(runner_module, "RUNNER_BACKEND", "inline")
    monkeypatch.setattr(runner_module, "_run_inline", _fake_inline)

    tool = OpteeRunnerTool()
    res = await tool.execute(
        workspace_id="ws",
        ta_dir="demo_ta",
        ca_dir="demo_ca",
        mode="build",
    )
    assert res.success
