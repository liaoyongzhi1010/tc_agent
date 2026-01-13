"""远程Embedding API"""
from typing import List
import httpx

from app.core.embedding.base import BaseEmbedding
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.embedding.remote")


class RemoteEmbedding(BaseEmbedding):
    """远程Embedding API(智谱/通义)"""

    PROVIDERS = {
        "zhipu": {
            "url": "https://open.bigmodel.cn/api/paas/v4/embeddings",
            "model": "embedding-2",
            "dimension": 1024,
        },
        "qwen": {
            "url": "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
            "model": "text-embedding-v2",
            "dimension": 1536,
        },
    }

    def __init__(self, provider: str = "zhipu", api_key: str = None):
        self.provider = provider
        self.api_key = api_key
        self.config = self.PROVIDERS.get(provider, self.PROVIDERS["zhipu"])
        self._dimension = self.config["dimension"]
        logger.info("远程Embedding已配置", provider=provider)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> List[float]:
        """生成单个文本的embedding"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            if self.provider == "zhipu":
                response = await client.post(
                    self.config["url"],
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.config["model"], "input": text},
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]

            elif self.provider == "qwen":
                response = await client.post(
                    self.config["url"],
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.config["model"],
                        "input": {"texts": [text]},
                        "parameters": {"text_type": "query"},
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["output"]["embeddings"][0]["embedding"]

            else:
                raise ValueError(f"Unknown provider: {self.provider}")

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成embeddings"""
        if not texts:
            return []

        # 大多数API支持批量,但这里简化为循环处理
        # 可以后续优化为真正的批量请求
        results = []
        for text in texts:
            embedding = await self.embed(text)
            results.append(embedding)
        return results
