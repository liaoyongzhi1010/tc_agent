"""文件操作工具"""
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from app.tools.base import BaseTool
from app.schemas.models import ToolResult
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.file")


class FileReadTool(BaseTool):
    """读取文件内容"""

    name = "file_read"
    description = "读取指定路径的文件内容"

    async def execute(
        self,
        path: str,
        encoding: str = "utf-8",
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        try:
            if cancel_event and cancel_event.is_set():
                return ToolResult(success=False, error="已取消")

            file_path = Path(path)
            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}")

            if not file_path.is_file():
                return ToolResult(success=False, error=f"不是文件: {path}")

            content = file_path.read_text(encoding=encoding)
            logger.debug("读取文件", path=path, size=len(content))

            return ToolResult(
                success=True,
                data={"path": path, "content": content, "size": len(content)},
            )
        except Exception as e:
            logger.error("读取文件失败", path=path, error=str(e))
            return ToolResult(success=False, error=str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "path": {"type": "string", "description": "文件路径"},
            "encoding": {"type": "string", "description": "编码(默认utf-8)"},
        }


class FileWriteTool(BaseTool):
    """写入文件内容"""

    name = "file_write"
    description = "将内容写入指定路径的文件"

    async def execute(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        try:
            if cancel_event and cancel_event.is_set():
                return ToolResult(success=False, error="已取消")

            file_path = Path(path)

            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            file_path.write_text(content, encoding=encoding)
            logger.info("写入文件", path=path, size=len(content))

            return ToolResult(
                success=True,
                data={"path": path, "size": len(content)},
            )
        except Exception as e:
            logger.error("写入文件失败", path=path, error=str(e))
            return ToolResult(success=False, error=str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"},
            "encoding": {"type": "string", "description": "编码(默认utf-8)"},
            "create_dirs": {"type": "boolean", "description": "自动创建目录(默认true)"},
        }
