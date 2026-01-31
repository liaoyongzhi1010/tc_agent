"""OP-TEE build & run tool (docker-based)."""
import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger
from app.infrastructure.workspace import get_workspace_path, safe_join
from app.infrastructure.runner_queue import RunnerQueue

logger = get_logger("tc_agent.tools.optee_runner")


RUNNER_BACKEND = os.getenv("TC_AGENT_RUNNER_BACKEND", "inline").strip().lower()
POLL_INTERVAL = float(os.getenv("TC_AGENT_RUNNER_POLL_INTERVAL", "1.0"))


class OpteeRunnerTool(BaseTool):
    """在Docker中编译/运行 OP-TEE 项目"""

    name = "optee_runner"
    description = "在Docker中编译/运行 OP-TEE 项目(需要后端工作区同步)"

    async def execute(
        self,
        workspace_id: str,
        ta_dir: str,
        ca_dir: Optional[str] = None,
        ca_bin: Optional[str] = None,
        mode: str = "full",
        timeout: int = 1200,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        if cancel_event and cancel_event.is_set():
            return ToolResult(success=False, error="已取消")

        payload = {
            "workspace_id": workspace_id,
            "ta_dir": ta_dir,
            "ca_dir": ca_dir,
            "ca_bin": ca_bin,
            "mode": mode,
            "timeout": timeout,
        }

        if RUNNER_BACKEND == "redis":
            return await _enqueue_and_wait(payload, timeout)

        return await _run_inline(**payload)

    def get_schema(self) -> Dict[str, Any]:
        return {
            "workspace_id": {"type": "string", "description": "后端工作区ID"},
            "ta_dir": {"type": "string", "description": "TA目录(相对工作区)"},
            "ca_dir": {"type": "string", "description": "CA目录(相对工作区)"},
            "ca_bin": {"type": "string", "description": "CA可执行文件路径(相对工作区,可选)"},
            "mode": {
                "type": "string",
                "enum": ["build", "test", "full"],
                "description": "执行模式: build/test/full",
            },
            "timeout": {"type": "number", "description": "超时秒数(默认1200)"},
        }


async def _enqueue_and_wait(payload: dict, timeout: int) -> ToolResult:
    try:
        queue = RunnerQueue()
        job_id = queue.enqueue(payload)
        result = queue.wait(job_id, timeout=timeout, poll=POLL_INTERVAL)
        if not result:
            return ToolResult(success=False, error="Runner超时或未启动")
        if result.get("status") == "failed":
            return ToolResult(success=False, error=result.get("error", "Runner失败"))
        raw = result.get("result")
        if raw:
            data = json.loads(raw)
            if data.get("success"):
                return ToolResult(success=True, data=data.get("data"))
            return ToolResult(success=False, error=data.get("error", "Runner失败"), data=data.get("data"))
        return ToolResult(success=False, error="Runner返回为空")
    except Exception as exc:
        logger.error("Runner队列失败", error=str(exc))
        return ToolResult(success=False, error=str(exc))


async def _run_inline(
    workspace_id: str,
    ta_dir: str,
    ca_dir: Optional[str] = None,
    ca_bin: Optional[str] = None,
    mode: str = "full",
    timeout: int = 1200,
) -> ToolResult:
    try:
        image = os.getenv("TC_AGENT_OPTEE_IMAGE", "tc-agent/optee-build:4.0")
        workspace_path = get_workspace_path(workspace_id)
        if not workspace_path.exists():
            return ToolResult(success=False, error="工作区不存在，请先同步")

        ta_abs = safe_join(workspace_path, ta_dir)
        ca_abs = safe_join(workspace_path, ca_dir) if ca_dir else None

        def run_cmd(cmd: str) -> subprocess.CompletedProcess:
            logger.info("Runner exec", cmd=cmd)
            return subprocess.run(
                cmd,
                shell=True,
                cwd=str(workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )

        def docker_cmd(inner: str) -> str:
            return (
                f"docker run --rm -v {shlex.quote(str(workspace_path))}:/workspace "
                f"{shlex.quote(image)} bash -lc {shlex.quote(inner)}"
            )

        outputs = []

        if mode in ("build", "full"):
            if not ta_abs.exists():
                return ToolResult(success=False, error=f"TA目录不存在: {ta_dir}")
            ta_cmd = docker_cmd(f"build_ta.sh /workspace/{ta_dir}")
            ta_res = run_cmd(ta_cmd)
            outputs.append(ta_res.stdout or "")
            if ta_res.returncode != 0:
                return ToolResult(
                    success=False,
                    error="TA 编译失败",
                    data={"log": _tail(outputs), "exit_code": ta_res.returncode},
                )

            if ca_abs and ca_abs.exists():
                ca_cmd = docker_cmd(f"build_ca.sh /workspace/{ca_dir}")
                ca_res = run_cmd(ca_cmd)
                outputs.append(ca_res.stdout or "")
                if ca_res.returncode != 0:
                    return ToolResult(
                        success=False,
                        error="CA 编译失败",
                        data={"log": _tail(outputs), "exit_code": ca_res.returncode},
                    )

        if mode in ("test", "full"):
            if not ca_dir:
                return ToolResult(success=False, error="缺少CA目录")

            if not ca_bin:
                ca_bin = _infer_ca_bin(ca_dir)

            test_cmd = docker_cmd(
                f"test_ta.sh /workspace/{ta_dir} /workspace/{ca_bin} /usr/bin/{Path(ca_bin).name} 300"
            )
            test_res = run_cmd(test_cmd)
            outputs.append(test_res.stdout or "")
            if test_res.returncode != 0:
                return ToolResult(
                    success=False,
                    error="运行测试失败",
                    data={"log": _tail(outputs), "exit_code": test_res.returncode},
                )

        return ToolResult(success=True, data={"log": _tail(outputs), "exit_code": 0})
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error="执行超时")
    except Exception as e:
        logger.error("执行失败", error=str(e))
        return ToolResult(success=False, error=str(e))


def _infer_ca_bin(ca_dir: str) -> str:
    name = Path(ca_dir).name
    if name.endswith("_ca"):
        name = name[:-3]
    return str(Path(ca_dir) / name)


def _tail(outputs: list[str], limit: int = 8000) -> str:
    text = "\n".join(outputs)
    if len(text) <= limit:
        return text
    return text[-limit:]
