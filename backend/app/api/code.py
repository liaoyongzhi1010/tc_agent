"""Code模式API - ReAct Agent执行"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
import json

from app.schemas.models import CodeExecuteRequest
from app.infrastructure.logger import get_logger

router = APIRouter()
logger = get_logger("tc_agent.api.code")

# 引用plan模块的workflows
from app.api.plan import workflows


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

        # TODO: 初始化ReAct Agent并执行
        # 目前发送占位消息
        for i, step in enumerate(workflow.steps):
            await websocket.send_json(
                {"type": "step_start", "step_index": i, "step": step.model_dump()}
            )

            # 模拟思考过程
            await websocket.send_json(
                {"type": "thought", "data": {"content": f"正在分析步骤: {step.description}"}}
            )

            # 模拟动作
            await websocket.send_json(
                {
                    "type": "action",
                    "data": {"tool": "placeholder", "input": {"step": step.description}},
                }
            )

            # 模拟观察
            await websocket.send_json(
                {"type": "observation", "data": {"content": f"步骤 {step.id} 执行完成"}}
            )

            await websocket.send_json({"type": "step_complete", "step_index": i})

        await websocket.send_json(
            {"type": "workflow_complete", "message": "所有步骤执行完成"}
        )

    except WebSocketDisconnect:
        logger.info("WebSocket断开连接", workflow_id=workflow_id)
    except Exception as e:
        logger.error("执行出错", error=str(e))
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()


@router.post("/execute-direct")
async def execute_direct(body: CodeExecuteRequest):
    """直接执行任务(不经过Plan模式),返回SSE流"""
    if not body.task:
        raise HTTPException(status_code=400, detail="Task required")

    logger.info("直接执行任务", task=body.task[:50])

    async def generate():
        # TODO: 使用ReAct Agent执行任务
        # 目前返回占位消息
        yield f"data: {json.dumps({'type': 'thought', 'data': {'content': f'分析任务: {body.task}'}})}\n\n"
        yield f"data: {json.dumps({'type': 'action', 'data': {'tool': 'placeholder', 'input': {}}})}\n\n"
        yield f"data: {json.dumps({'type': 'observation', 'data': {'content': '执行完成'}})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'data': {'answer': 'ReAct Agent尚未完全集成'}})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
