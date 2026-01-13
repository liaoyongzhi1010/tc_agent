"""工具基类"""
from abc import ABC, abstractmethod
from typing import Any, Dict

from app.schemas.models import ToolResult


class BaseTool(ABC):
    """工具抽象基类"""

    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """返回工具参数schema，供LLM理解"""
        pass

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"
