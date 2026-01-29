"""Agent执行API - ReAct Agent执行"""
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.infrastructure.logger import get_logger
from app.core.llm import LLMFactory
from app.core.agent import ReActAgent
from app.tools.registry import ToolRegistry

router = APIRouter()
logger = get_logger("tc_agent.api.code")

# 引用plan模块的workflows
from app.api.plan import workflows

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
    await websocket.accept()
    logger.info("Agent执行WebSocket连接", workflow_id=workflow_id)
    cancel_event = asyncio.Event()
    receiver_task: asyncio.Task | None = None

    try:
        if workflow_id not in workflows:
            await websocket.send_json({"type": "error", "message": "Workflow not found"})
            await websocket.close()
            return

        workflow = workflows[workflow_id]
        if workflow.status != "confirmed":
            await websocket.send_json({"type": "error", "message": "Workflow not confirmed"})
            await websocket.close()
            return

        async def _receive():
            while True:
                try:
                    message = await websocket.receive_json()
                except WebSocketDisconnect:
                    cancel_event.set()
                    break
                except Exception:
                    cancel_event.set()
                    break
                if message.get("type") == "cancel":
                    cancel_event.set()
                    break

        receiver_task = asyncio.create_task(_receive())

        # 创建并运行ReAct Agent
        agent = get_react_agent()

        async for event in agent.run(
            workflow.task, workflow, workflow.workspace_root, cancel_event
        ):
            logger.info("发送事件", event_type=event.type)
            await websocket.send_json({"type": event.type, "data": event.data})
            if event.type == "cancelled":
                break

    except WebSocketDisconnect:
        logger.info("WebSocket断开连接", workflow_id=workflow_id)
    except Exception as e:
        logger.error("执行出错", error=str(e))
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if receiver_task:
            receiver_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
