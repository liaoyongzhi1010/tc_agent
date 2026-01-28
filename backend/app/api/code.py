"""Code模式API - ReAct Agent执行"""
import asyncio
import uuid
from typing import Dict

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

# 正在运行的任务（run_id -> cancel_event）
_active_runs: Dict[str, asyncio.Event] = {}


def _create_run() -> tuple[str, asyncio.Event]:
    run_id = str(uuid.uuid4())
    cancel_event = asyncio.Event()
    _active_runs[run_id] = cancel_event
    return run_id, cancel_event


def _cleanup_run(run_id: str) -> None:
    _active_runs.pop(run_id, None)


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
    run_id, cancel_event = _create_run()
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
        await websocket.send_json({"type": "run_id", "data": {"run_id": run_id}})

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
        _cleanup_run(run_id)
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/execute-direct")
async def execute_direct(body: CodeExecuteRequest):
    """直接执行任务(不经过Plan模式),返回SSE流"""
    if not body.task:
        raise HTTPException(status_code=400, detail="Task required")

    run_id, cancel_event = _create_run()
    logger.info("直接执行任务", task=body.task[:50], workspace=body.workspace_root, run_id=run_id)

    async def generate():
        try:
            agent = get_react_agent()
            yield f"data: {json.dumps({'type': 'run_id', 'data': {'run_id': run_id}}, ensure_ascii=False)}\n\n"

            async for event in agent.run(
                body.task, workspace_root=body.workspace_root, cancel_event=cancel_event
            ):
                yield f"data: {json.dumps({'type': event.type, 'data': event.data}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("执行出错", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"
        finally:
            _cleanup_run(run_id)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/cancel/{run_id}")
async def cancel_run(run_id: str):
    """取消正在运行的任务"""
    cancel_event = _active_runs.get(run_id)
    if not cancel_event:
        raise HTTPException(status_code=404, detail="Run not found")
    cancel_event.set()
    return {"status": "cancel_requested", "run_id": run_id}


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
