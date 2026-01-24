"""OP-TEE Docker编译工具"""
import asyncio
import os
from pathlib import Path
from typing import Dict, Any

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

    async def execute(
        self,
        source_dir: str,
        build_type: str = "ta",
        output_dir: str = None,
    ) -> ToolResult:
        """
        执行Docker编译

        Args:
            source_dir: 源代码目录（包含Makefile）
            build_type: 编译类型，ta或ca
            output_dir: 输出目录（可选，默认为source_dir）
        """
        try:
            source_path = Path(source_dir).resolve()
            if not source_path.exists():
                return ToolResult(success=False, error=f"源代码目录不存在: {source_dir}")

            if build_type not in ("ta", "ca"):
                return ToolResult(success=False, error="build_type必须是'ta'或'ca'")

            output_path = Path(output_dir).resolve() if output_dir else source_path

            # 检查Docker是否可用
            check_result = await self._run_command("docker --version")
            if check_result["returncode"] != 0:
                return ToolResult(success=False, error="Docker不可用，请确保Docker已安装并运行")

            # 检查镜像是否存在，不存在则构建
            image_exists = await self._check_image_exists()
            if not image_exists:
                logger.info("Docker镜像不存在，开始构建...")
                build_result = await self._build_image()
                if not build_result["success"]:
                    return ToolResult(success=False, error=f"构建Docker镜像失败: {build_result['error']}")
                logger.info("Docker镜像构建完成")

            # 执行编译
            if build_type == "ta":
                result = await self._build_ta(source_path, output_path)
            else:
                result = await self._build_ca(source_path, output_path)

            return result

        except Exception as e:
            logger.error("Docker编译失败", error=str(e))
            return ToolResult(success=False, error=str(e))

    async def _check_image_exists(self) -> bool:
        """检查Docker镜像是否存在"""
        result = await self._run_command(f"docker images -q {OPTEE_IMAGE_NAME}")
        return bool(result["stdout"].strip())

    async def _build_image(self) -> Dict[str, Any]:
        """构建Docker镜像"""
        # 获取Dockerfile所在目录
        backend_dir = Path(__file__).parent.parent.parent.parent
        dockerfile_full_path = backend_dir / DOCKERFILE_PATH

        if not dockerfile_full_path.exists():
            return {"success": False, "error": f"Dockerfile不存在: {dockerfile_full_path}"}

        docker_dir = dockerfile_full_path.parent
        cmd = f"docker build -t {OPTEE_IMAGE_NAME} -f {dockerfile_full_path} {docker_dir}"

        logger.info("开始构建Docker镜像", cmd=cmd)
        result = await self._run_command(cmd, timeout=1800)  # 30分钟超时

        if result["returncode"] != 0:
            return {"success": False, "error": result["stderr"] or result["stdout"]}

        return {"success": True}

    async def _build_ta(self, source_path: Path, output_path: Path) -> ToolResult:
        """编译TA"""
        # Docker运行命令
        cmd = (
            f"docker run --rm "
            f"-v {source_path}:/workspace/ta "
            f"-v {output_path}:/workspace/output "
            f"-w /workspace/ta "
            f"{OPTEE_IMAGE_NAME} "
            f"bash -c 'make CROSS_COMPILE=aarch64-linux-gnu- "
            f"TA_DEV_KIT_DIR=/optee/optee_os/out/arm-plat-vexpress/export-ta_arm64 "
            f"-j$(nproc) && cp -f *.ta /workspace/output/ 2>/dev/null || true'"
        )

        logger.info("编译TA", source=str(source_path))
        result = await self._run_command(cmd, timeout=300)

        if result["returncode"] != 0:
            return ToolResult(
                success=False,
                error=f"TA编译失败:\n{result['stderr'] or result['stdout']}"
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

    async def _build_ca(self, source_path: Path, output_path: Path) -> ToolResult:
        """编译CA"""
        cmd = (
            f"docker run --rm "
            f"-v {source_path}:/workspace/ca "
            f"-v {output_path}:/workspace/output "
            f"-w /workspace/ca "
            f"{OPTEE_IMAGE_NAME} "
            f"bash -c 'make CROSS_COMPILE=aarch64-linux-gnu- "
            f"TEEC_EXPORT=/optee/optee_client/out/export/usr "
            f"-j$(nproc) && find . -maxdepth 1 -type f -executable -exec cp {{}} /workspace/output/ \\;'"
        )

        logger.info("编译CA", source=str(source_path))
        result = await self._run_command(cmd, timeout=300)

        if result["returncode"] != 0:
            return ToolResult(
                success=False,
                error=f"CA编译失败:\n{result['stderr'] or result['stdout']}"
            )

        return ToolResult(
            success=True,
            data={
                "message": "CA编译成功",
                "output_dir": str(output_path),
            }
        )

    async def _run_command(self, cmd: str, timeout: int = 120) -> Dict[str, Any]:
        """运行shell命令"""
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
            return {
                "returncode": -1,
                "stdout": "",
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
        }
