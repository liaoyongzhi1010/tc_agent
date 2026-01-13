"""知识库管理API"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
import tempfile

from app.schemas.models import AddDocumentRequest, AddDirectoryRequest
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


@router.post("/add-directory")
async def add_directory(body: AddDirectoryRequest):
    """扫描目录添加代码文件"""
    dir_path = Path(body.path)
    if not dir_path.exists():
        raise HTTPException(status_code=400, detail="Directory not found")

    logger.info("扫描目录", path=body.path, patterns=body.file_patterns)

    try:
        vector_store = await get_vector_store()
        count = await vector_store.add_from_directory(
            directory=dir_path,
            collection=body.collection,
            patterns=body.file_patterns,
        )
        return {"status": "success", "documents_added": count}
    except Exception as e:
        logger.error("扫描目录失败", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), collection: str = "text"):
    """上传文件到知识库"""
    logger.info("上传文件", filename=file.filename, collection=collection)

    try:
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)

        # 读取内容
        content = tmp_path.read_text(encoding="utf-8")

        # 添加到向量存储
        vector_store = await get_vector_store()
        await vector_store.add_documents(
            collection=collection,
            documents=[content],
            metadatas=[{"source": file.filename, "filename": file.filename}],
        )

        # 清理临时文件
        tmp_path.unlink()

        return {"status": "success", "filename": file.filename}
    except Exception as e:
        logger.error("上传文件失败", error=str(e))
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
