"""Embedding抽象基类"""
from abc import ABC, abstractmethod
from typing import List


class BaseEmbedding(ABC):
    """Embedding抽象基类"""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """生成单个文本的embedding"""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成embeddings"""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回embedding维度"""
        pass
