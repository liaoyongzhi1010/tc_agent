"""TC Agent Backend - FastAPI入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import ask, plan, code, knowledge
from app.infrastructure.config import settings
from app.infrastructure.logger import get_logger
from app.infrastructure.vector_store import get_vector_store

logger = get_logger("tc_agent.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("TC Agent后端启动中...", host=settings.host, port=settings.port)

    # 初始化向量存储
    try:
        vector_store = await get_vector_store()
        logger.info("向量存储初始化完成")

        # 加载预置知识库
        await vector_store.load_preset_knowledge()
        stats = await vector_store.get_stats()
        logger.info("预置知识库加载完成", stats=stats)
    except Exception as e:
        logger.warning("向量存储初始化失败(可继续使用)", error=str(e))

    logger.info("TC Agent后端启动完成")
    yield

    # 清理资源
    logger.info("TC Agent后端关闭中...")


CORS_ALLOW_ORIGIN_REGEX = r"^vscode-webview://.*$|^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app = FastAPI(
    title="TC Agent Backend",
    description="可信计算开发助手后端服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS配置(仅允许本地VS Code插件访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(ask.router, prefix="/ask", tags=["Ask Mode"])
app.include_router(plan.router, prefix="/plan", tags=["Plan Mode"])
app.include_router(code.router, prefix="/code", tags=["Code Mode"])
app.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge"])


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "llm_provider": settings.llm_provider,
        "embedding_mode": settings.embedding_mode,
    }


@app.get("/config")
async def get_config():
    """获取当前配置(不含敏感信息)"""
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.get_default_model(),
        "embedding_mode": settings.embedding_mode,
        "embedding_model": settings.embedding_model,
        "rag_child_chunk_size": settings.rag_child_chunk_size,
        "rag_parent_chunk_size": settings.rag_parent_chunk_size,
        "rag_top_k": settings.rag_top_k,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
