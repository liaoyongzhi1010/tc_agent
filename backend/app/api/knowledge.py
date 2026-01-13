"""知识库管理API"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path

from app.schemas.models import AddDocumentRequest, AddDirectoryRequest
from app.infrastructure.logger import get_logger

router = APIRouter()
logger = get_logger("tc_agent.api.knowledge")


@router.post("/add-document")
async def add_document(body: AddDocumentRequest):
    """添加单个文档"""
    logger.info("添加文档", collection=body.collection, content_len=len(body.content))

    # TODO: 集成VectorStore
    return {"status": "success", "message": "文档已添加(VectorStore尚未集成)"}


@router.post("/add-directory")
async def add_directory(body: AddDirectoryRequest):
    """扫描目录添加代码文件"""
    dir_path = Path(body.path)
    if not dir_path.exists():
        raise HTTPException(status_code=400, detail="Directory not found")

    logger.info("扫描目录", path=body.path, patterns=body.file_patterns)

    # TODO: 集成VectorStore扫描目录
    return {"status": "success", "documents_added": 0, "message": "VectorStore尚未集成"}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), collection: str = "text"):
    """上传文件到知识库"""
    logger.info("上传文件", filename=file.filename, collection=collection)

    # TODO: 集成VectorStore
    return {"status": "success", "filename": file.filename, "message": "VectorStore尚未集成"}


@router.get("/stats")
async def get_stats():
    """获取知识库统计"""
    # TODO: 集成VectorStore
    return {
        "text": {"name": "tc_agent_text_knowledge", "count": 0},
        "code": {"name": "tc_agent_code_knowledge", "count": 0},
    }


@router.delete("/collection/{name}")
async def delete_collection(name: str):
    """删除知识库集合"""
    logger.info("删除集合", collection=name)

    # TODO: 集成VectorStore
    return {"status": "success", "message": f"集合 {name} 已删除(VectorStore尚未集成)"}
