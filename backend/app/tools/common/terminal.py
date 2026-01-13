"""终端执行工具"""
import asyncio
from typing import Dict, Any

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.terminal")


class TerminalTool(BaseTool):
    """执行终端命令"""

    name = "terminal"
    description = "在终端执行命令并返回输出"

    async def execute(
        self, command: str, cwd: str = None, timeout: int = 60
    ) -> ToolResult:
        try:
            logger.info("执行命令", command=command[:100], cwd=cwd)

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(success=False, error=f"命令执行超时({timeout}秒)")

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if process.returncode == 0:
                return ToolResult(
                    success=True,
                    data={
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                        "return_code": process.returncode,
                    },
                )
            else:
                return ToolResult(
                    success=False,
                    data={
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                        "return_code": process.returncode,
                    },
                    error=f"命令返回非零退出码: {process.returncode}",
                )

        except Exception as e:
            logger.error("执行命令失败", command=command[:100], error=str(e))
            return ToolResult(success=False, error=str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "command": {"type": "string", "description": "要执行的命令"},
            "cwd": {"type": "string", "description": "工作目录(可选)"},
            "timeout": {"type": "integer", "description": "超时时间(秒,默认60)"},
        }
