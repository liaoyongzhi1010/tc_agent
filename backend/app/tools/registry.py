"""工具注册表"""
import os
from typing import Dict, List, Optional, Set

from app.tools.base import BaseTool
from app.infrastructure.config import settings
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.registry")


class ToolRegistry:
    """工具注册表，支持动态注册和分类管理"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(self, tool: BaseTool, category: str = "common") -> None:
        """注册工具"""
        self._tools[tool.name] = tool
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool.name)
        logger.debug("工具已注册", name=tool.name, category=category)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """获取某类别的所有工具"""
        names = self._categories.get(category, [])
        return [self._tools[name] for name in names if name in self._tools]

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())

    def get_tools_prompt(self) -> str:
        """生成工具描述供LLM使用"""
        lines = []
        for category, names in self._categories.items():
            if names:
                lines.append(f"\n## {category.upper()} Tools:")
                for name in names:
                    tool = self._tools.get(name)
                    if tool:
                        lines.append(f"\n### {tool.name}")
                        lines.append(f"描述: {tool.description}")
                        lines.append("参数:")
                        schema = tool.get_schema()
                        for param, info in schema.items():
                            param_type = info.get("type", "string")
                            param_desc = info.get("description", "")
                            lines.append(f"  - {param} ({param_type}): {param_desc}")
        return "\n".join(lines)

    def load_all_tools(self) -> None:
        """加载所有内置工具"""
        packs = _parse_tool_packs()

        if "core" in packs:
            from app.tools.common.file import FileReadTool, FileWriteTool
            from app.tools.tee.ta_generator import TAGenerator
            from app.tools.tee.ca_generator import CAGenerator
            from app.tools.tee.crypto import CryptoHelper

            self.register(FileReadTool(), "core")
            self.register(FileWriteTool(), "core")
            self.register(TAGenerator(), "core")
            self.register(CAGenerator(), "core")
            self.register(CryptoHelper(), "core")

        if "runner" in packs:
            from app.tools.tee.optee_runner import OpteeRunnerTool

            self.register(OpteeRunnerTool(), "runner")

        logger.info("工具加载完成", total=len(self._tools), packs=list(packs))


def _parse_tool_packs() -> Set[str]:
    raw = os.getenv("TC_AGENT_TOOL_PACKS") or settings.tool_packs or "core"
    return {p.strip() for p in raw.split(",") if p.strip()}
