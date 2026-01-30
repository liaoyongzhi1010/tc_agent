"""RAG检索器抽象基类"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict

from app.schemas.models import RetrievedDoc


class BaseRetriever(ABC):
    """RAG检索器抽象基类，扩展时继承此类"""

    @abstractmethod
    async def retrieve(
        self, query: str, top_k: int = 5, where: Optional[Dict[str, str]] = None
    ) -> List[RetrievedDoc]:
        """检索相关文档"""
        pass

    @abstractmethod
    async def add_documents(
        self, documents: List[str], metadatas: List[dict]
    ) -> None:
        """添加文档到知识库"""
        pass

    @abstractmethod
    async def delete_documents(self, ids: List[str]) -> None:
        """删除文档"""
        pass
