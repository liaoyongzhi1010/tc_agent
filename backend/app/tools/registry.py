"""工具注册表"""
from typing import Dict, List, Optional

from app.tools.base import BaseTool
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.tools.registry")


class ToolRegistry:
    """工具注册表，支持动态注册和分类管理"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, List[str]] = {"common": [], "tee": []}

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
        # 加载通用工具
        from app.tools.common.file import FileReadTool, FileWriteTool
        from app.tools.common.terminal import TerminalTool

        self.register(FileReadTool(), "common")
        self.register(FileWriteTool(), "common")
        self.register(TerminalTool(), "common")

        # 加载TEE工具
        from app.tools.tee.ta_generator import TAGenerator
        from app.tools.tee.ca_generator import CAGenerator
        from app.tools.tee.crypto import CryptoHelper
        from app.tools.tee.docker_build import DockerBuildTool
        from app.tools.tee.ta_validate import TAValidateTool
        from app.tools.tee.qemu_run import QemuRunTool
        from app.tools.tee.workflow_runner import WorkflowRunner

        self.register(TAGenerator(), "tee")
        self.register(CAGenerator(), "tee")
        self.register(CryptoHelper(), "tee")
        self.register(DockerBuildTool(), "tee")
        self.register(TAValidateTool(), "tee")
        self.register(QemuRunTool(), "tee")
        self.register(WorkflowRunner(), "tee")

        logger.info("工具加载完成", total=len(self._tools))
