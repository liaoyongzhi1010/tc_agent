"""Agent执行API - ReAct Agent执行"""

from fastapi import APIRouter, WebSocket
from app.infrastructure.logger import get_logger
from app.core.llm import LLMFactory
from app.core.agent import ReActAgent
from app.tools.registry import ToolRegistry
from app.infrastructure.workflow_store import get_workflow_store
from app.api.code_session import CodeSession

router = APIRouter()
logger = get_logger("tc_agent.api.code")

# 初始化工具注册表
_tool_registry: ToolRegistry = None

def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        _tool_registry.load_all_tools()
    return _tool_registry


def get_react_agent() -> ReActAgent:
    """创建ReAct Agent"""
    llm = LLMFactory.create_from_config()
    tools = get_tool_registry()
    return ReActAgent(llm, tools)


@router.websocket("/execute/{workflow_id}")
async def execute_workflow(websocket: WebSocket, workflow_id: str):
    """WebSocket连接执行workflow"""
    session = CodeSession(
        websocket=websocket,
        workflow_id=workflow_id,
        workflow_store=get_workflow_store(),
        agent_factory=get_react_agent,
    )
    await session.run()
