"""Code模式API - ReAct Agent执行"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
import json

from app.schemas.models import CodeExecuteRequest
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
    logger.info("Code模式WebSocket连接", workflow_id=workflow_id)

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

        # 创建并运行ReAct Agent
        agent = get_react_agent()

        async for event in agent.run(workflow.task, workflow):
            await websocket.send_json({"type": event.type, "data": event.data})

    except WebSocketDisconnect:
        logger.info("WebSocket断开连接", workflow_id=workflow_id)
    except Exception as e:
        logger.error("执行出错", error=str(e))
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/execute-direct")
async def execute_direct(body: CodeExecuteRequest):
    """直接执行任务(不经过Plan模式),返回SSE流"""
    if not body.task:
        raise HTTPException(status_code=400, detail="Task required")

    logger.info("直接执行任务", task=body.task[:50])

    async def generate():
        try:
            agent = get_react_agent()

            async for event in agent.run(body.task):
                yield f"data: {json.dumps({'type': event.type, 'data': event.data}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("执行出错", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/tools")
async def list_tools():
    """列出所有可用工具"""
    tools = get_tool_registry()
    return {
        "tools": [
            {"name": t.name, "description": t.description, "schema": t.get_schema()}
            for t in tools.get_all_tools()
        ]
    }
