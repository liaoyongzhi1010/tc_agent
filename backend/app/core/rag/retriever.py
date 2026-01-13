"""Parent Document Retriever实现"""
import hashlib
from typing import List, Dict, Optional
import uuid as uuid_lib

from app.core.rag.base import BaseRetriever
from app.core.rag.chunker import BaseChunker, TextChunker
from app.core.embedding.base import BaseEmbedding
from app.schemas.models import RetrievedDoc
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.rag.retriever")


class ParentDocumentRetriever(BaseRetriever):
    """
    Parent Document Retriever实现

    策略: Small-to-Big Retrieval
    - 用小chunk做检索(更精确匹配)
    - 返回大chunk/完整文档(更多上下文)
    """

    def __init__(
        self,
        collection,  # Chroma collection
        embedding: BaseEmbedding,
        chunker: BaseChunker = None,
        parent_store: Dict[str, dict] = None,
        child_chunk_size: int = 200,
        parent_chunk_size: int = 1000,
    ):
        """
        Args:
            collection: Chroma collection实例
            embedding: Embedding模型
            chunker: 文档切分器
            parent_store: 存储parent文档的字典
            child_chunk_size: child chunk大小(用于检索)
            parent_chunk_size: parent chunk大小(用于返回)
        """
        self.collection = collection
        self.embedding = embedding
        self.chunker = chunker or TextChunker()
        self.parent_store = parent_store if parent_store is not None else {}
        self.child_chunk_size = child_chunk_size
        self.parent_chunk_size = parent_chunk_size

    async def add_documents(
        self, documents: List[str], metadatas: List[dict]
    ) -> None:
        """添加文档,同时构建parent和child索引"""
        for doc, meta in zip(documents, metadatas):
            if not doc or not doc.strip():
                continue

            # 生成文档ID
            doc_id = hashlib.md5(doc.encode()).hexdigest()[:16]

            # 切分为parent chunks
            parent_chunks = self.chunker.chunk(doc, self.parent_chunk_size)

            for i, parent_chunk in enumerate(parent_chunks):
                if not parent_chunk.strip():
                    continue

                parent_id = f"{doc_id}_p{i}"

                # 存储parent到内存
                self.parent_store[parent_id] = {
                    "content": parent_chunk,
                    "metadata": {**meta, "chunk_index": i, "parent_id": parent_id},
                }

                # 将parent切分为child chunks
                child_chunker = TextChunker()
                child_chunks = child_chunker.chunk(parent_chunk, self.child_chunk_size)

                if not child_chunks:
                    child_chunks = [parent_chunk]

                # 批量生成embeddings
                child_embeddings = await self.embedding.embed_batch(child_chunks)

                # 存储到Chroma
                child_ids = [f"{parent_id}_c{j}" for j in range(len(child_chunks))]
                child_metadatas = [
                    {
                        "parent_id": parent_id,
                        "source": meta.get("source", ""),
                        "child_index": j,
                    }
                    for j in range(len(child_chunks))
                ]

                self.collection.add(
                    ids=child_ids,
                    embeddings=child_embeddings,
                    documents=child_chunks,
                    metadatas=child_metadatas,
                )

        logger.debug("文档已索引", doc_count=len(documents))

    async def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDoc]:
        """检索相关文档"""
        if not query or not query.strip():
            return []

        # 生成query embedding
        query_embedding = await self.embedding.embed(query)

        # 在child chunks中检索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 3,  # 多检索一些,去重后取top_k
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        # 收集唯一的parent_ids
        seen_parents = set()
        retrieved_docs = []

        for i, child_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            parent_id = meta.get("parent_id")

            if not parent_id or parent_id in seen_parents:
                continue
            seen_parents.add(parent_id)

            # 获取parent文档
            parent_data = self.parent_store.get(parent_id)
            if parent_data:
                # 将distance转换为相似度分数 (cosine distance -> similarity)
                distance = results["distances"][0][i]
                score = 1.0 / (1.0 + distance)

                retrieved_docs.append(
                    RetrievedDoc(
                        content=parent_data["content"],
                        metadata={
                            **parent_data["metadata"],
                            "matched_child": results["documents"][0][i][:100],
                        },
                        score=score,
                    )
                )

            if len(retrieved_docs) >= top_k:
                break

        logger.debug(
            "检索完成", query=query[:30], results=len(retrieved_docs)
        )
        return retrieved_docs

    async def delete_documents(self, ids: List[str]) -> None:
        """删除文档"""
        # 删除child chunks
        for doc_id in ids:
            # 找到所有相关的child ids
            results = self.collection.get(
                where={"parent_id": {"$regex": f"^{doc_id}"}}
            )
            if results["ids"]:
                self.collection.delete(ids=results["ids"])

            # 删除parent store中的记录
            to_delete = [k for k in self.parent_store if k.startswith(doc_id)]
            for k in to_delete:
                del self.parent_store[k]

        logger.debug("文档已删除", count=len(ids))
