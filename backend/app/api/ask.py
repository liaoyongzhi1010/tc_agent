"""Ask模式API - RAG问答"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json

from app.schemas.models import AskRequest, AskResponse
from app.infrastructure.logger import get_logger
from app.infrastructure.vector_store import get_vector_store
from app.core.llm import LLMFactory

router = APIRouter()
logger = get_logger("tc_agent.api.ask")


def build_ask_prompt(query: str, context: str) -> str:
    """构建Ask模式的prompt"""
    return f"""你是一个可信计算领域的专家助手，专注于OP-TEE、TrustZone等技术。请基于以下参考资料回答用户问题。

参考资料:
{context}

用户问题: {query}

请基于参考资料给出准确、专业的回答。如果参考资料中没有相关信息，请明确说明并基于你的知识给出回答。回答时：
1. 使用中文回答
2. 如果涉及代码，请提供完整可用的示例
3. 解释关键概念和步骤
"""


@router.post("/", response_model=AskResponse)
async def ask_question(request: Request, body: AskRequest):
    """非流式问答"""
    logger.info("收到Ask请求", query=body.query[:50])

    try:
        # 获取向量存储
        vector_store = await get_vector_store()
        retriever = vector_store.get_retriever(body.knowledge_type or "all")

        # RAG检索
        docs = await retriever.retrieve(body.query, top_k=5)
        logger.debug("RAG检索完成", results=len(docs))

        # 构建上下文
        if docs:
            context = "\n\n---\n\n".join(
                [
                    f"[来源: {d.metadata.get('source', 'unknown')}]\n{d.content}"
                    for d in docs
                ]
            )
        else:
            context = "（未找到相关参考资料）"

        # LLM生成
        llm = LLMFactory.create_from_config()
        prompt = build_ask_prompt(body.query, context)
        answer = await llm.generate(prompt)

        return AskResponse(
            answer=answer,
            sources=[
                {"source": d.metadata.get("source", ""), "score": d.score}
                for d in docs
            ],
        )

    except Exception as e:
        logger.error("Ask请求处理失败", error=str(e))
        return AskResponse(
            answer=f"处理请求时出错: {str(e)}\n\n请检查配置和API Key是否正确。",
            sources=[],
        )


@router.post("/stream")
async def ask_question_stream(request: Request, body: AskRequest):
    """流式问答(SSE)"""
    logger.info("收到Ask流式请求", query=body.query[:50])

    async def generate():
        try:
            # 获取向量存储
            vector_store = await get_vector_store()
            retriever = vector_store.get_retriever(body.knowledge_type or "all")

            # RAG检索
            docs = await retriever.retrieve(body.query, top_k=5)

            # 发送来源信息
            sources_data = [
                {"source": d.metadata.get("source", ""), "score": d.score}
                for d in docs
            ]
            yield f"data: {json.dumps({'type': 'sources', 'data': sources_data}, ensure_ascii=False)}\n\n"

            # 构建上下文
            if docs:
                context = "\n\n---\n\n".join(
                    [
                        f"[来源: {d.metadata.get('source', 'unknown')}]\n{d.content}"
                        for d in docs
                    ]
                )
            else:
                context = "（未找到相关参考资料）"

            # 流式生成回答
            llm = LLMFactory.create_from_config()
            prompt = build_ask_prompt(body.query, context)

            async for chunk in llm.stream(prompt):
                yield f"data: {json.dumps({'type': 'content', 'data': chunk}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error("流式Ask请求处理失败", error=str(e))
            error_msg = f"处理请求时出错: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
