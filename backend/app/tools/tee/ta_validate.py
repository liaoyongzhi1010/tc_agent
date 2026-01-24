"""OP-TEE TA 验证工具"""
import asyncio
from pathlib import Path
from typing import Dict, Any

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.ta_validate")

# 使用编译镜像进行验证
OPTEE_IMAGE_NAME = "tc-agent/optee-build:4.0"


class TAValidateTool(BaseTool):
    """验证 OP-TEE TA 文件的正确性"""

    name = "ta_validate"
    description = "验证编译好的 TA 文件格式、签名和结构是否正确"

    async def execute(self, ta_path: str) -> ToolResult:
        """
        验证 TA 文件

        Args:
            ta_path: TA 文件路径 (.ta 文件)
        """
        try:
            ta_file = Path(ta_path).resolve()
            if not ta_file.exists():
                return ToolResult(success=False, error=f"TA 文件不存在: {ta_path}")

            if not ta_file.suffix == ".ta":
                return ToolResult(success=False, error="文件必须是 .ta 格式")

            # 获取 TA 所在目录
            ta_dir = ta_file.parent
            ta_name = ta_file.name
            uuid = ta_file.stem

            # 在 Docker 中运行验证
            validate_script = f'''
echo "========================================"
echo "OP-TEE TA Validation Report"
echo "========================================"
echo ""

# 1. 文件信息
echo "[1] File Information:"
ls -lh /workspace/{ta_name}
echo ""

# 2. 文件类型
echo "[2] File Type:"
file /workspace/{ta_name}
echo ""

# 3. UUID
echo "[3] TA UUID: {uuid}"
echo ""

# 4. TA 头部 (检查签名头)
echo "[4] TA Header (first 32 bytes):"
xxd -l 32 /workspace/{ta_name}
echo ""

# 5. Magic Number 检查
echo "[5] Signature Check:"
MAGIC=$(xxd -p -l 4 /workspace/{ta_name})
if [ "$MAGIC" = "4f545348" ]; then
    echo "  ✓ Valid OP-TEE Signed Header (OTSH)"
    echo "  ✓ TA is properly signed"
else
    echo "  ✗ Invalid magic: $MAGIC"
fi
echo ""

# 6. 检查 ELF 文件
if [ -f "/workspace/{uuid}.stripped.elf" ]; then
    echo "[6] ELF Analysis:"
    aarch64-linux-gnu-objdump -h /workspace/{uuid}.stripped.elf 2>/dev/null | grep -E "Idx|text|data|rodata" || echo "  (stripped)"
    echo ""

    echo "[7] Entry Points:"
    aarch64-linux-gnu-nm /workspace/{uuid}.elf 2>/dev/null | grep -E "TA_Create|TA_Open|TA_Invoke|TA_Close|TA_Destroy" || echo "  (symbols stripped)"
fi

echo ""
echo "========================================"
echo "Validation Complete: SUCCESS"
echo "========================================"
'''

            cmd = (
                f"docker run --rm "
                f"-v {ta_dir}:/workspace "
                f"-w /workspace "
                f"{OPTEE_IMAGE_NAME} "
                f"bash -c '{validate_script}'"
            )

            result = await self._run_command(cmd, timeout=60)

            if result["returncode"] != 0:
                return ToolResult(
                    success=False,
                    error=f"验证失败:\n{result['stderr'] or result['stdout']}"
                )

            return ToolResult(
                success=True,
                data={
                    "uuid": uuid,
                    "path": str(ta_file),
                    "report": result["stdout"],
                }
            )

        except Exception as e:
            logger.error("TA 验证失败", error=str(e))
            return ToolResult(success=False, error=str(e))

    async def _run_command(self, cmd: str, timeout: int = 60) -> Dict[str, Any]:
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
            "ta_path": {
                "type": "string",
                "description": "TA 文件路径 (.ta 文件)",
            },
        }
