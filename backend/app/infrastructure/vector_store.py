"""Chroma向量存储管理器"""
import asyncio
import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Optional, Dict

from app.core.embedding import EmbeddingFactory, BaseEmbedding
from app.core.rag.retriever import ParentDocumentRetriever
from app.core.rag.chunker import TextChunker, CodeChunker
from app.schemas.models import RetrievedDoc
from app.infrastructure.config import settings
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.vector_store")


class VectorStoreManager:
    """Chroma向量存储管理器"""

    COLLECTIONS = {
        "text": "tc_agent_text_knowledge",
        "code": "tc_agent_code_knowledge",
    }

    def __init__(self):
        self.client: Optional[chromadb.Client] = None
        self.embedding: Optional[BaseEmbedding] = None
        self.retrievers: Dict[str, ParentDocumentRetriever] = {}
        self._parent_stores: Dict[str, dict] = {"text": {}, "code": {}}
        self._initialized = False

    async def initialize(self) -> None:
        """初始化向量存储"""
        if self._initialized:
            return

        # 初始化Chroma客户端(持久化存储)
        db_path = settings.data_dir / "chroma_db"
        db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )

        # 初始化Embedding
        self.embedding = EmbeddingFactory.create_from_config()

        # 创建或获取collections并创建retrievers
        for key, name in self.COLLECTIONS.items():
            collection = self.client.get_or_create_collection(
                name=name, metadata={"hnsw:space": "cosine"}
            )

            # 为每个collection创建retriever
            chunker = CodeChunker() if key == "code" else TextChunker()
            self.retrievers[key] = ParentDocumentRetriever(
                collection=collection,
                embedding=self.embedding,
                chunker=chunker,
                parent_store=self._parent_stores[key],
                child_chunk_size=settings.rag_child_chunk_size,
                parent_chunk_size=settings.rag_parent_chunk_size,
            )

        self._initialized = True
        logger.info("向量存储初始化完成", db_path=str(db_path))

    async def load_preset_knowledge(self) -> None:
        """加载预置知识库"""
        preset_dir = Path(__file__).parent.parent.parent / "knowledge"

        # Ask 知识
        ask_docs = preset_dir / "ask" / "docs"
        if ask_docs.exists():
            count = await self._load_directory(
                ask_docs, "text", ["*.md", "*.txt"], {"scope": "ask"}
            )
            logger.info("预置文本知识加载完成(ask)", count=count)

        ask_code = preset_dir / "ask" / "code"
        if ask_code.exists():
            count = await self._load_directory(
                ask_code, "code", ["*.c", "*.h", "*.py"], {"scope": "ask"}
            )
            logger.info("预置代码知识加载完成(ask)", count=count)

        # Plan 知识
        plan_docs = preset_dir / "plan" / "docs"
        if plan_docs.exists():
            count = await self._load_directory(
                plan_docs, "text", ["*.md", "*.txt"], {"scope": "plan"}
            )
            logger.info("预置文本知识加载完成(plan)", count=count)

        plan_code = preset_dir / "plan" / "code"
        if plan_code.exists():
            count = await self._load_directory(
                plan_code, "code", ["*.c", "*.h", "*.py"], {"scope": "plan"}
            )
            logger.info("预置代码知识加载完成(plan)", count=count)

    async def _load_directory(
        self,
        directory: Path,
        collection: str,
        patterns: List[str],
        extra_metadata: Optional[dict] = None,
    ) -> int:
        """加载目录下的文件"""
        count = 0
        for pattern in patterns:
            for file_path in directory.rglob(pattern):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if content.strip():
                        metadata = {
                            "source": str(file_path),
                            "filename": file_path.name,
                            "type": file_path.suffix,
                        }
                        if extra_metadata:
                            metadata.update(extra_metadata)
                        await self.add_documents(
                            collection=collection,
                            documents=[content],
                            metadatas=[metadata],
                        )
                        count += 1
                except Exception as e:
                    logger.warning("文件加载失败", file=str(file_path), error=str(e))
        return count

    def get_retriever(self, collection_type: str = "all") -> ParentDocumentRetriever:
        """获取检索器"""
        if collection_type == "all":
            return MultiCollectionRetriever(list(self.retrievers.values()))
        return self.retrievers.get(collection_type, self.retrievers.get("text"))

    async def add_documents(
        self, collection: str, documents: List[str], metadatas: List[dict]
    ) -> None:
        """添加文档到知识库"""
        retriever = self.retrievers.get(collection)
        if not retriever:
            raise ValueError(f"Unknown collection: {collection}")

        await retriever.add_documents(documents, metadatas)
        logger.info("文档已添加", collection=collection, count=len(documents))

    async def add_from_directory(
        self,
        directory: Path,
        collection: str,
        patterns: List[str],
        extra_metadata: Optional[dict] = None,
    ) -> int:
        """从目录添加文件"""
        return await self._load_directory(
            directory, collection, patterns, extra_metadata
        )

    async def add_file(self, file_path: Path, collection: str) -> None:
        """添加单个文件"""
        content = file_path.read_text(encoding="utf-8")
        await self.add_documents(
            collection=collection,
            documents=[content],
            metadatas=[{"source": str(file_path), "filename": file_path.name}],
        )

    async def get_stats(self) -> dict:
        """获取知识库统计信息"""
        stats = {}
        for key, name in self.COLLECTIONS.items():
            try:
                collection = self.client.get_collection(name)
                stats[key] = {"name": name, "count": collection.count()}
            except Exception:
                stats[key] = {"name": name, "count": 0}
        return stats

    async def delete_collection(self, collection: str) -> None:
        """删除并重建集合"""
        name = self.COLLECTIONS.get(collection)
        if name:
            try:
                self.client.delete_collection(name)
            except Exception:
                pass
            # 重新创建空集合
            self.client.get_or_create_collection(name)
            # 清空parent store
            self._parent_stores[collection] = {}
            logger.info("集合已重置", collection=collection)

    async def close(self) -> None:
        """关闭资源"""
        self._initialized = False


class MultiCollectionRetriever:
    """多集合联合检索器"""

    def __init__(self, retrievers: List[ParentDocumentRetriever]):
        self.retrievers = retrievers

    async def retrieve(
        self, query: str, top_k: int = 5, where: Optional[dict] = None
    ) -> List[RetrievedDoc]:
        """从所有集合检索并合并结果"""
        all_results = []

        for retriever in self.retrievers:
            try:
                results = await retriever.retrieve(query, top_k=top_k, where=where)
                all_results.extend(results)
            except Exception as e:
                logger.warning("检索失败", error=str(e))

        # 按分数排序,取top_k
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:top_k]

    async def add_documents(
        self, documents: List[str], metadatas: List[dict]
    ) -> None:
        """添加到第一个retriever(默认text)"""
        if self.retrievers:
            await self.retrievers[0].add_documents(documents, metadatas)

    async def delete_documents(self, ids: List[str]) -> None:
        """从所有retriever删除"""
        for retriever in self.retrievers:
            await retriever.delete_documents(ids)


# 全局实例
_vector_store: Optional[VectorStoreManager] = None
_vector_store_lock = asyncio.Lock()


async def get_vector_store() -> VectorStoreManager:
    """获取向量存储实例(单例)"""
    global _vector_store
    if _vector_store is not None and _vector_store._initialized:
        return _vector_store

    async with _vector_store_lock:
        if _vector_store is None:
            manager = VectorStoreManager()
            await manager.initialize()
            _vector_store = manager
        elif not _vector_store._initialized:
            await _vector_store.initialize()
    return _vector_store
