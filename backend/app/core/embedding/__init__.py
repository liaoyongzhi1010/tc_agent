"""Embedding模块"""
from typing import Optional

from app.core.embedding.base import BaseEmbedding
from app.core.embedding.local import LocalEmbedding
from app.core.embedding.remote import RemoteEmbedding
from app.infrastructure.config import settings


class EmbeddingFactory:
    """Embedding工厂"""

    @staticmethod
    def create(
        mode: str = None,
        model_name: str = None,
        api_key: str = None,
        provider: str = None,
    ) -> BaseEmbedding:
        """创建Embedding实例

        Args:
            mode: 模式 ("local" 或 "remote")
            model_name: 本地模型名称
            api_key: 远程API Key
            provider: 远程提供商 ("zhipu" 或 "qwen")
        """
        mode = mode or settings.embedding_mode

        if mode == "local":
            model = model_name or settings.embedding_model
            return LocalEmbedding(model_name=model)

        elif mode == "remote":
            key = api_key or settings.embedding_api_key or settings.get_llm_api_key()
            prov = provider or settings.llm_provider
            return RemoteEmbedding(provider=prov, api_key=key)

        else:
            raise ValueError(f"Unknown embedding mode: {mode}")

    @staticmethod
    def create_from_config() -> BaseEmbedding:
        """从配置创建Embedding实例"""
        return EmbeddingFactory.create()


__all__ = ["BaseEmbedding", "LocalEmbedding", "RemoteEmbedding", "EmbeddingFactory"]
