"""LLM抽象层"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List

from app.schemas.models import LLMConfig


class BaseLLM(ABC):
    """LLM抽象基类"""

    @abstractmethod
    async def generate(self, prompt: str, config: LLMConfig = None) -> str:
        """同步生成"""
        pass

    @abstractmethod
    async def stream(self, prompt: str, config: LLMConfig = None) -> AsyncIterator[str]:
        """流式生成"""
        pass

    @abstractmethod
    async def generate_chat(self, messages: List[dict], config: LLMConfig = None) -> str:
        """聊天生成"""
        pass
