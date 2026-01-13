"""LLM模块"""
from typing import Optional

from app.core.llm.base import BaseLLM
from app.core.llm.qwen import QwenLLM
from app.core.llm.zhipu import ZhipuLLM
from app.infrastructure.config import settings


class LLMFactory:
    """LLM工厂"""

    @staticmethod
    def create(provider: str = None, api_key: str = None, model: str = None) -> BaseLLM:
        """创建LLM实例"""
        provider = provider or settings.llm_provider
        model = model or settings.get_default_model()

        if provider == "qwen":
            key = api_key or settings.qwen_api_key
            return QwenLLM(api_key=key, model=model)
        elif provider == "zhipu":
            key = api_key or settings.zhipu_api_key
            return ZhipuLLM(api_key=key, model=model)
        elif provider == "doubao":
            # TODO: 实现豆包LLM
            raise NotImplementedError("Doubao LLM not implemented yet")
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def create_from_config() -> BaseLLM:
        """从配置创建LLM实例"""
        return LLMFactory.create()


__all__ = ["BaseLLM", "QwenLLM", "ZhipuLLM", "LLMFactory"]
