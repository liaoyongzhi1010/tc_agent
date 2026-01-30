"""OP-TEE Docker编译工具"""
import asyncio
import os
import shlex
import signal
from pathlib import Path
from typing import Dict, Any, Optional

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.docker_build")

# Docker镜像名称
OPTEE_IMAGE_NAME = "tc-agent/optee-build:4.0"
# Dockerfile路径（相对于backend目录）
DOCKERFILE_PATH = "docker/Dockerfile.optee"


class DockerBuildTool(BaseTool):
    """使用Docker容器编译OP-TEE TA/CA代码"""

    name = "docker_build"
    description = "使用Docker容器编译OP-TEE TA或CA代码。支持编译TA(.ta文件)和CA(可执行文件)"

    def _classify_build_error(self, stderr: str, stdout: str) -> str:
        text = f"{stderr}\n{stdout}".lower()
        if "超时" in text or "timeout" in text:
            return "timeout"
        if "undefined reference" in text or "collect2" in text or "ld:" in text:
            return "link_error"
        if "error:" in text or "fatal error" in text or "no rule to make target" in text:
            return "compile_error"
        return "compile_error"

    def _list_executables(self, directory: Path) -> list[Path]:
        return [
            path
            for path in directory.iterdir()
            if path.is_file() and os.access(path, os.X_OK)
        ]

    async def execute(
        self,
        source_dir: str,
        build_type: str = "ta",
        output_dir: str = None,
        ta_dir: str = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        """
        执行Docker编译

        Args:
            source_dir: 源代码目录（包含Makefile）
            build_type: 编译类型，ta或ca
            output_dir: 输出目录（可选，默认为source_dir）
        """
        try:
            if cancel_event and cancel_event.is_set():
                return ToolResult(success=False, error="已取消")

            source_path = Path(source_dir).resolve()
            if not source_path.exists():
                return ToolResult(success=False, error=f"源代码目录不存在: {source_dir}")

            if build_type not in ("ta", "ca"):
                return ToolResult(success=False, error="build_type必须是'ta'或'ca'")

            output_path = Path(output_dir).resolve() if output_dir else source_path

            # 检查Docker是否可用
            check_result = await self._run_command("docker --version", cancel_event=cancel_event)
            if check_result["returncode"] != 0:
                return ToolResult(success=False, error="Docker不可用，请确保Docker已安装并运行")

            # 检查镜像是否存在，不存在则构建
            image_exists = await self._check_image_exists(cancel_event=cancel_event)
            if not image_exists:
                logger.info("Docker镜像不存在，开始构建...")
                build_result = await self._build_image(cancel_event=cancel_event)
                if not build_result["success"]:
                    return ToolResult(
                        success=False,
                        error=f"构建Docker镜像失败: {build_result['error']}",
                        data={
                            "stage": "build_image",
                            "error_type": self._classify_build_error(
                                build_result.get("error", ""), ""
                            ),
                            "stderr": build_result.get("error", ""),
                        },
                    )
                logger.info("Docker镜像构建完成")

            # 执行编译
            if build_type == "ta":
                result = await self._build_ta(source_path, output_path, cancel_event=cancel_event)
            else:
                ta_path = Path(ta_dir).resolve() if ta_dir else None
                result = await self._build_ca(source_path, output_path, ta_path, cancel_event=cancel_event)

            return result

        except Exception as e:
            logger.error("Docker编译失败", error=str(e))
            return ToolResult(success=False, error=str(e))

    async def _check_image_exists(self, cancel_event: Optional[asyncio.Event] = None) -> bool:
        """检查Docker镜像是否存在"""
        result = await self._run_command(
            f"docker images -q {OPTEE_IMAGE_NAME}", cancel_event=cancel_event
        )
        return bool(result["stdout"].strip())

    async def _build_image(self, cancel_event: Optional[asyncio.Event] = None) -> Dict[str, Any]:
        """构建Docker镜像"""
        # 获取Dockerfile所在目录
        backend_dir = Path(__file__).parent.parent.parent.parent
        dockerfile_full_path = backend_dir / DOCKERFILE_PATH

        if not dockerfile_full_path.exists():
            return {"success": False, "error": f"Dockerfile不存在: {dockerfile_full_path}"}

        docker_dir = dockerfile_full_path.parent
        cmd = (
            f"docker build -t {OPTEE_IMAGE_NAME} "
            f"-f {shlex.quote(str(dockerfile_full_path))} {shlex.quote(str(docker_dir))}"
        )

        logger.info("开始构建Docker镜像", cmd=cmd)
        result = await self._run_command(cmd, timeout=1800, cancel_event=cancel_event)  # 30分钟超时

        if result["returncode"] != 0:
            return {"success": False, "error": result["stderr"] or result["stdout"]}

        return {"success": True}

    async def _build_ta(
        self,
        source_path: Path,
        output_path: Path,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        """编译TA"""
        # Docker运行命令
        cmd = (
            f"docker run --rm "
            f"-v {shlex.quote(str(source_path))}:{shlex.quote('/workspace/ta')} "
            f"-v {shlex.quote(str(output_path))}:{shlex.quote('/workspace/output')} "
            f"-w /workspace/ta "
            f"{OPTEE_IMAGE_NAME} "
            f"bash -c 'make CROSS_COMPILE=aarch64-linux-gnu- "
            f"TA_DEV_KIT_DIR=/optee/optee_os/out/arm-plat-vexpress/export-ta_arm64 "
            f"-j$(nproc) && cp -f *.ta /workspace/output/ 2>/dev/null || true'"
        )

        logger.info("编译TA", source=str(source_path))
        result = await self._run_command(cmd, timeout=300, cancel_event=cancel_event)

        if result["returncode"] != 0:
            return ToolResult(
                success=False,
                error=f"TA编译失败:\n{result['stderr'] or result['stdout']}",
                data={
                    "stage": "build_ta",
                    "error_type": self._classify_build_error(
                        result.get("stderr", ""), result.get("stdout", "")
                    ),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode"),
                },
            )

        # 查找生成的.ta文件
        ta_files = list(output_path.glob("*.ta"))
        if ta_files:
            return ToolResult(
                success=True,
                data={
                    "message": "TA编译成功",
                    "output_files": [str(f) for f in ta_files],
                    "output_dir": str(output_path),
                }
            )
        else:
            # 检查源目录是否有.ta文件
            ta_in_source = list(source_path.glob("*.ta"))
            if ta_in_source:
                return ToolResult(
                    success=True,
                    data={
                        "message": "TA编译成功",
                        "output_files": [str(f) for f in ta_in_source],
                        "output_dir": str(source_path),
                    }
                )
            return ToolResult(
                success=False,
                error="编译完成但未找到.ta文件，请检查Makefile配置"
            )

    def _build_ca_command(
        self, source_path: Path, output_path: Path, ta_path: Optional[Path]
    ) -> str:
        extra_mount = ""
        if ta_path:
            if not ta_path.exists():
                raise FileNotFoundError(f"TA 目录不存在: {ta_path}")
            extra_mount = (
                f"-v {shlex.quote(str(ta_path))}:{shlex.quote(f'/workspace/{ta_path.name}')} "
            )
        return (
            f"docker run --rm "
            f"-v {shlex.quote(str(source_path))}:{shlex.quote('/workspace/ca')} "
            f"-v {shlex.quote(str(output_path))}:{shlex.quote('/workspace/output')} "
            f"{extra_mount}"
            f"-w /workspace/ca "
            f"{OPTEE_IMAGE_NAME} "
            f"bash -c 'make CROSS_COMPILE=aarch64-linux-gnu- "
            f"TEEC_EXPORT=/optee/optee_client/out/export/usr "
            f"-j$(nproc) && find . -maxdepth 1 -type f -executable -exec cp {{}} /workspace/output/ \\;'"
        )

    async def _build_ca(
        self,
        source_path: Path,
        output_path: Path,
        ta_path: Optional[Path],
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        """编译CA"""
        cmd = self._build_ca_command(source_path, output_path, ta_path)

        logger.info("编译CA", source=str(source_path))
        result = await self._run_command(cmd, timeout=300, cancel_event=cancel_event)

        if result["returncode"] != 0:
            return ToolResult(
                success=False,
                error=f"CA编译失败:\n{result['stderr'] or result['stdout']}",
                data={
                    "stage": "build_ca",
                    "error_type": self._classify_build_error(
                        result.get("stderr", ""), result.get("stdout", "")
                    ),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode"),
                },
            )

        executables = self._list_executables(output_path)
        if len(executables) != 1:
            return ToolResult(
                success=False,
                error=(
                    f"CA编译完成但可执行文件数量={len(executables)}，"
                    "请确保输出目录仅包含一个可执行文件"
                ),
                data={
                    "stage": "build_ca",
                    "error_type": "build_output_invalid",
                    "output_dir": str(output_path),
                    "executables": [str(path) for path in executables],
                },
            )

        return ToolResult(
            success=True,
            data={
                "message": "CA编译成功",
                "output_dir": str(output_path),
                "executables": [str(executables[0])],
            }
        )

    async def _run_command(
        self,
        cmd: str,
        timeout: int = 120,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> Dict[str, Any]:
        """运行shell命令"""
        try:
            if cancel_event and cancel_event.is_set():
                return {"returncode": -2, "stdout": "", "stderr": "已取消"}

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            def terminate(proc: asyncio.subprocess.Process) -> None:
                if proc.returncode is not None:
                    return
                try:
                    if hasattr(os, "killpg"):
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                except ProcessLookupError:
                    pass

            communicate_task = asyncio.create_task(process.communicate())
            cancel_task = None
            tasks = [communicate_task]
            if cancel_event:
                cancel_task = asyncio.create_task(cancel_event.wait())
                tasks.append(cancel_task)

            done, _ = await asyncio.wait(
                tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            status = "timeout"
            if cancel_task and cancel_task in done:
                status = "cancelled"
                terminate(process)
            elif communicate_task in done:
                status = "done"
            else:
                terminate(process)

            try:
                stdout, stderr = await communicate_task
            finally:
                if cancel_task and cancel_task not in done:
                    cancel_task.cancel()

            if status == "cancelled":
                return {
                    "returncode": -2,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": "已取消",
                }
            if status == "done":
                return {
                    "returncode": process.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                }
            return {
                "returncode": -1,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": f"命令执行超时({timeout}秒)",
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "source_dir": {
                "type": "string",
                "description": "源代码目录路径（包含Makefile的TA或CA目录）",
            },
            "build_type": {
                "type": "string",
                "enum": ["ta", "ca"],
                "description": "编译类型：ta(Trusted Application)或ca(Client Application)",
            },
            "output_dir": {
                "type": "string",
                "description": "输出目录（可选，默认与源代码目录相同）",
            },
            "ta_dir": {
                "type": "string",
                "description": "TA 目录路径（CA 编译时可选，含头文件）",
            },
        }
