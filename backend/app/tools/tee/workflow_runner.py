"""Workflow runner helpers for TA/CA build + QEMU test."""
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.infrastructure.config import settings
from app.infrastructure.logger import get_logger
from app.schemas.models import ToolResult
from app.tools.base import BaseTool
from app.tools.tee.docker_build import DockerBuildTool
from app.tools.tee.qemu_run import QemuRunTool

logger = get_logger("tc_agent.tools.workflow_runner")


def evaluate_qemu_output(output: str, require_ca: bool) -> Dict[str, Any]:
    """Evaluate QEMU output markers to determine success."""
    has_complete = "TEST_COMPLETE" in output
    ca_marker = "CA_EXIT_CODE=" in output
    ca_ok = "CA_EXIT_CODE=0" in output

    if not has_complete:
        return {"success": False, "reason": "missing TEST_COMPLETE marker"}
    if require_ca and not ca_marker:
        return {"success": False, "reason": "missing CA_EXIT_CODE"}
    if require_ca and not ca_ok:
        return {"success": False, "reason": "CA_EXIT_CODE not zero"}
    return {"success": True, "reason": "ok"}


def find_executable_file(directory: Path) -> Path:
    """Find a single executable file in the directory."""
    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file() and os.access(path, os.X_OK)
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError("No executable file found")
    raise ValueError("Multiple executables found")


class WorkflowRunner(BaseTool):
    """Compile TA/CA and run QEMU tests in a single flow."""

    name = "workflow_runner"
    description = "编译TA/CA并在QEMU中运行测试，返回结构化结果，支持secure模式CA端到端校验"

    async def execute(
        self,
        ta_dir: str,
        ca_dir: Optional[str] = None,
        timeout: int = 120,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        if cancel_event and cancel_event.is_set():
            return ToolResult(success=False, error="已取消", data={"stage": "cancelled"})

        secure_mode = settings.qemu_mode == "secure"
        require_ca = secure_mode

        if require_ca and not ca_dir:
            return ToolResult(
                success=False,
                error="secure模式必须提供ca_dir",
                data={"stage": "precheck"},
            )

        docker_build = DockerBuildTool()
        qemu_run = QemuRunTool()

        ta_build = await docker_build.execute(
            source_dir=ta_dir, build_type="ta", cancel_event=cancel_event
        )
        if not ta_build.success:
            return ToolResult(
                success=False,
                error=ta_build.error or "TA编译失败",
                data={"stage": "build_ta", "details": ta_build.data},
            )

        ca_exe_path: Optional[Path] = None
        if ca_dir:
            ca_build = await docker_build.execute(
                source_dir=ca_dir,
                build_type="ca",
                ta_dir=ta_dir,
                cancel_event=cancel_event,
            )
            if not ca_build.success:
                return ToolResult(
                    success=False,
                    error=ca_build.error or "CA编译失败",
                    data={"stage": "build_ca", "details": ca_build.data},
                )
            try:
                ca_exe_path = find_executable_file(Path(ca_dir))
            except ValueError as exc:
                return ToolResult(
                    success=False,
                    error=str(exc),
                    data={"stage": "ca_resolve"},
                )

        if settings.qemu_test_command:
            test_command = settings.qemu_test_command
        elif secure_mode and ca_exe_path:
            test_command = f"/usr/bin/{ca_exe_path.name}"
        else:
            test_command = "echo TA loaded successfully"

        ca_file = str(ca_exe_path) if ca_exe_path else None

        qemu_result = await qemu_run.execute(
            ta_dir=ta_dir,
            test_command=test_command,
            timeout=timeout,
            secure_mode=secure_mode,
            ca_file=ca_file,
            cancel_event=cancel_event,
        )

        if not qemu_result.success:
            return ToolResult(
                success=False,
                error=qemu_result.error or "QEMU测试失败",
                data={"stage": "qemu_run", "details": qemu_result.data},
            )

        output = ""
        if isinstance(qemu_result.data, dict):
            output = qemu_result.data.get("output", "") or ""

        evaluation = evaluate_qemu_output(output, require_ca=require_ca)
        if not evaluation["success"]:
            return ToolResult(
                success=False,
                error=f"QEMU输出校验失败: {evaluation['reason']}",
                data={"stage": "qemu_run", "output": output},
            )

        logger.info(
            "WorkflowRunner完成",
            ta_dir=ta_dir,
            ca_dir=ca_dir,
            mode="secure" if secure_mode else "simple",
        )

        return ToolResult(
            success=True,
            data={
                "stage": "complete",
                "mode": "secure" if secure_mode else "simple",
                "ta_dir": ta_dir,
                "ca_dir": ca_dir,
                "output": output,
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "ta_dir": {"type": "string", "description": "TA 目录路径"},
            "ca_dir": {"type": "string", "description": "CA 目录路径（secure模式必填）"},
            "timeout": {"type": "integer", "description": "超时时间(秒)"},
        }
