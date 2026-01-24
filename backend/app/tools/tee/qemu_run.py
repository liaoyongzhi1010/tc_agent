"""QEMU OP-TEE 运行工具 - 在 QEMU 中测试 TA"""
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.qemu_run")

OPTEE_IMAGE_NAME = "tc-agent/optee-build:4.0"


class QemuRunTool(BaseTool):
    """在 QEMU 模拟器中运行和测试 OP-TEE TA"""

    name = "qemu_run"
    description = "在 QEMU ARM64 模拟器中启动 OP-TEE 环境，加载并测试 TA。可以看到实际运行输出。"

    async def execute(
        self,
        ta_dir: str,
        test_command: str = "ls /lib/optee_armtz/",
        timeout: int = 120,  # Mac Docker 环境需要更长时间
        interactive: bool = False,
        secure_mode: bool = False,  # True: ATF+TrustZone (Linux), False: 简化模式 (Mac)
        ca_file: str = None,
    ) -> ToolResult:
        """
        在 QEMU 中运行 TA 测试

        Args:
            ta_dir: TA 文件所在目录
            test_command: 在 QEMU 中执行的测试命令
            timeout: 超时时间（秒）
            interactive: 是否交互模式（需要手动退出）
            secure_mode: 安全模式，True 使用 ATF+TrustZone（Linux），False 使用简化模式（Mac）
        """
        try:
            ta_path = Path(ta_dir).resolve()
            if not ta_path.exists():
                return ToolResult(success=False, error=f"TA 目录不存在: {ta_dir}")

            # 检查是否有 .ta 文件
            ta_files = list(ta_path.glob("*.ta"))
            if not ta_files:
                return ToolResult(success=False, error=f"目录中没有 .ta 文件: {ta_dir}")

            ca_path = None
            if ca_file:
                ca_path = Path(ca_file).resolve()
                if not ca_path.exists():
                    return ToolResult(success=False, error=f"CA 文件不存在: {ca_file}")

            # 检查 Docker 镜像
            check_result = await self._run_command(f"docker images -q {OPTEE_IMAGE_NAME}")
            if not check_result["stdout"].strip():
                return ToolResult(
                    success=False,
                    error="Docker 镜像不存在，请先构建: docker build -t tc-agent/optee-build:4.0 -f docker/Dockerfile.optee docker/"
                )

            if interactive:
                # 交互模式 - 启动 QEMU shell
                qemu_script = "run_qemu.sh" if secure_mode else "run_qemu_simple.sh"
                ca_mount = ""
                ca_arg = ""
                if ca_path:
                    ca_mount = f"-v {ca_path.parent}:/workspace/ca "
                    ca_arg = f"/workspace/ca/{ca_path.name}"
                cmd = (
                    f"docker run --rm -it "
                    f"-v {ta_path}:/workspace/ta "
                    f"{ca_mount}"
                    f"{OPTEE_IMAGE_NAME} "
                    f"{qemu_script} /workspace/ta {ca_arg}"
                )
                mode_desc = "ATF+TrustZone 模式" if secure_mode else "简化模式（无 TrustZone）"
                return ToolResult(
                    success=True,
                    data={
                        "message": f"请在终端运行以下命令进入交互模式（{mode_desc}）：",
                        "command": cmd,
                        "exit_hint": "按 Ctrl+A 然后 X 退出 QEMU",
                        "mode": "secure" if secure_mode else "simple",
                    }
                )
            else:
                # 非交互模式 - 自动运行测试
                test_script = "test_ta.sh" if secure_mode else "test_ta_simple.sh"
                cmd = self._build_qemu_command(
                    ta_dir=ta_path,
                    test_script=test_script,
                    test_command=test_command,
                    timeout=timeout,
                    ca_file=ca_path,
                )

                mode_desc = "ATF+TrustZone" if secure_mode else "简化模式"
                logger.info(f"运行 QEMU 测试 ({mode_desc})", ta_dir=str(ta_path), command=test_command)
                result = await self._run_command(cmd, timeout=timeout + 30)

                if result["returncode"] != 0 and "Test Complete" not in result["stdout"]:
                    return ToolResult(
                        success=False,
                        error=f"QEMU 测试失败:\n{result['stderr'] or result['stdout']}"
                    )

                return ToolResult(
                    success=True,
                    data={
                        "ta_files": [str(f) for f in ta_files],
                        "test_command": test_command,
                        "output": result["stdout"],
                        "mode": "secure" if secure_mode else "simple",
                    }
                )

        except Exception as e:
            logger.error("QEMU 运行失败", error=str(e))
            return ToolResult(success=False, error=str(e))

    def _build_qemu_command(
        self,
        ta_dir: Path,
        test_script: str,
        test_command: str,
        timeout: int,
        ca_file: Optional[Path],
    ) -> str:
        ca_mount = ""
        ca_arg = ""
        if ca_file:
            ca_mount = f"-v {ca_file.parent}:/workspace/ca "
            ca_arg = f"/workspace/ca/{ca_file.name}"
        return (
            f"docker run --rm "
            f"-v {ta_dir}:/workspace/ta "
            f"{ca_mount}"
            f"{OPTEE_IMAGE_NAME} "
            f"{test_script} /workspace/ta {ca_arg} '{test_command}' {timeout}"
        )

    async def _run_command(self, cmd: str, timeout: int = 120) -> Dict[str, Any]:
        """运行 shell 命令"""
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except asyncio.TimeoutError:
            process.kill()
            return {"returncode": -1, "stdout": "", "stderr": f"超时({timeout}秒)"}
        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    def get_schema(self) -> Dict[str, Any]:
        return {
            "ta_dir": {
                "type": "string",
                "description": "TA 文件所在目录（包含 .ta 文件）",
            },
            "test_command": {
                "type": "string",
                "description": "在 QEMU 中执行的测试命令（默认列出已加载的 TA）",
            },
            "timeout": {
                "type": "integer",
                "description": "测试超时时间，单位秒（默认 120，Mac Docker 环境建议 120-180）",
            },
            "interactive": {
                "type": "boolean",
                "description": "是否交互模式，true 则返回手动运行命令（默认 false）",
            },
            "secure_mode": {
                "type": "boolean",
                "description": "安全模式：true 使用 ATF+TrustZone（Linux 生产环境），false 使用简化模式（Mac 开发环境，默认）",
            },
            "ca_file": {
                "type": "string",
                "description": "CA 可执行文件路径（可选）",
            },
        }
