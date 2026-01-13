"""Ask模式API - RAG问答"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json

from app.schemas.models import AskRequest, AskResponse
from app.infrastructure.logger import get_logger

router = APIRouter()
logger = get_logger("tc_agent.api.ask")


@router.post("/", response_model=AskResponse)
async def ask_question(request: Request, body: AskRequest):
    """非流式问答"""
    logger.info("收到Ask请求", query=body.query[:50])

    # TODO: 集成RAG检索和LLM生成
    # 目前返回占位响应
    return AskResponse(
        answer=f"收到问题: {body.query}\n\n这是一个占位响应，RAG系统尚未完全集成。",
        sources=[],
    )


@router.post("/stream")
async def ask_question_stream(request: Request, body: AskRequest):
    """流式问答(SSE)"""
    logger.info("收到Ask流式请求", query=body.query[:50])

    async def generate():
        # 发送来源信息
        yield f"data: {json.dumps({'type': 'sources', 'data': []})}\n\n"

        # 流式生成回答(占位)
        response = f"收到问题: {body.query}\n\n这是一个占位响应，RAG系统尚未完全集成。"
        for char in response:
            yield f"data: {json.dumps({'type': 'content', 'data': char})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
