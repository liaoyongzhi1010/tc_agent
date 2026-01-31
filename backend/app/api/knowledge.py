"""知识库管理API"""
from fastapi import APIRouter, HTTPException

from app.schemas.models import AddDocumentRequest
from app.infrastructure.logger import get_logger
from app.infrastructure.vector_store import get_vector_store

router = APIRouter()
logger = get_logger("tc_agent.api.knowledge")


@router.post("/add-document")
async def add_document(body: AddDocumentRequest):
    """添加单个文档"""
    logger.info("添加文档", collection=body.collection, content_len=len(body.content))

    try:
        vector_store = await get_vector_store()
        await vector_store.add_documents(
            collection=body.collection,
            documents=[body.content],
            metadatas=[body.metadata],
        )
        return {"status": "success", "message": "文档已添加"}
    except Exception as e:
        logger.error("添加文档失败", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """获取知识库统计"""
    try:
        vector_store = await get_vector_store()
        stats = await vector_store.get_stats()
        return stats
    except Exception as e:
        logger.error("获取统计失败", error=str(e))
        return {
            "text": {"name": "tc_agent_text_knowledge", "count": 0},
            "code": {"name": "tc_agent_code_knowledge", "count": 0},
            "error": str(e),
        }


@router.delete("/collection/{name}")
async def delete_collection(name: str):
    """删除知识库集合"""
    logger.info("删除集合", collection=name)

    try:
        vector_store = await get_vector_store()
        await vector_store.delete_collection(name)
        return {"status": "success", "message": f"集合 {name} 已删除"}
    except Exception as e:
        logger.error("删除集合失败", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload-preset")
async def reload_preset():
    """重新加载预置知识库"""
    logger.info("重新加载预置知识库")

    try:
        vector_store = await get_vector_store()
        await vector_store.load_preset_knowledge()
        stats = await vector_store.get_stats()
        return {"status": "success", "stats": stats}
    except Exception as e:
        logger.error("加载预置知识库失败", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
