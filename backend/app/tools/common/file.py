"""文件操作工具（由前端执行）"""
import asyncio
from typing import Dict, Any, Optional

from app.tools.base import BaseTool
from app.schemas.models import ToolResult


class FileReadTool(BaseTool):
    """读取文件内容"""

    name = "file_read"
    description = "读取工作区文件内容（由前端执行）"

    async def execute(
        self,
        path: str,
        encoding: str = "utf-8",
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        if cancel_event and cancel_event.is_set():
            return ToolResult(success=False, error="已取消")
        return ToolResult(success=False, error="file_read 仅支持前端执行")

    def get_schema(self) -> Dict[str, Any]:
        return {
            "path": {"type": "string", "description": "文件路径"},
            "encoding": {"type": "string", "description": "编码(默认utf-8)"},
        }


class FileWriteTool(BaseTool):
    """写入文件内容"""

    name = "file_write"
    description = "将内容写入工作区文件（由前端执行）"

    async def execute(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        if cancel_event and cancel_event.is_set():
            return ToolResult(success=False, error="已取消")
        return ToolResult(success=False, error="file_write 仅支持前端执行")

    def get_schema(self) -> Dict[str, Any]:
        return {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"},
            "encoding": {"type": "string", "description": "编码(默认utf-8)"},
            "create_dirs": {"type": "boolean", "description": "自动创建目录(默认true)"},
        }
