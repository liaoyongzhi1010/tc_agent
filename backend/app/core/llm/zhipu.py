"""智谱GLM LLM"""
from typing import AsyncIterator, List
from zhipuai import ZhipuAI

from app.core.llm.base import BaseLLM
from app.schemas.models import LLMConfig
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.llm.zhipu")


class ZhipuLLM(BaseLLM):
    """智谱GLM LLM实现"""

    def __init__(self, api_key: str, model: str = "glm-4-flash"):
        self.client = ZhipuAI(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, config: LLMConfig = None) -> str:
        """同步生成"""
        model = config.model if config else self.model
        temperature = config.temperature if config else 0.7

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        return response.choices[0].message.content

    async def stream(self, prompt: str, config: LLMConfig = None) -> AsyncIterator[str]:
        """流式生成"""
        model = config.model if config else self.model
        temperature = config.temperature if config else 0.7

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=True,
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def generate_chat(self, messages: List[dict], config: LLMConfig = None) -> str:
        """聊天生成"""
        model = config.model if config else self.model
        temperature = config.temperature if config else 0.7

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        return response.choices[0].message.content
