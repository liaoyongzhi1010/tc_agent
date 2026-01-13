"""本地Embedding模型"""
import asyncio
from typing import List

from app.core.embedding.base import BaseEmbedding
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.embedding.local")


class LocalEmbedding(BaseEmbedding):
    """本地Embedding模型(sentence-transformers)"""

    _model_cache = {}  # 模型缓存,避免重复加载

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name
        self._model = None
        self._dimension = None

    def _get_model(self):
        """懒加载模型"""
        if self._model is None:
            if self.model_name in self._model_cache:
                self._model = self._model_cache[self.model_name]
            else:
                try:
                    from sentence_transformers import SentenceTransformer

                    logger.info("加载本地Embedding模型", model=self.model_name)
                    self._model = SentenceTransformer(self.model_name)
                    self._model_cache[self.model_name] = self._model
                    logger.info("模型加载完成", model=self.model_name)
                except Exception as e:
                    logger.error("模型加载失败", model=self.model_name, error=str(e))
                    raise
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            model = self._get_model()
            self._dimension = model.get_sentence_embedding_dimension()
        return self._dimension

    async def embed(self, text: str) -> List[float]:
        """生成单个文本的embedding"""
        loop = asyncio.get_event_loop()
        model = self._get_model()

        embedding = await loop.run_in_executor(
            None, lambda: model.encode(text, normalize_embeddings=True)
        )
        return embedding.tolist()

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成embeddings"""
        if not texts:
            return []

        loop = asyncio.get_event_loop()
        model = self._get_model()

        embeddings = await loop.run_in_executor(
            None, lambda: model.encode(texts, normalize_embeddings=True)
        )
        return embeddings.tolist()
