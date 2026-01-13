"""通义千问LLM"""
import asyncio
from typing import AsyncIterator, List
import dashscope
from dashscope import Generation

from app.core.llm.base import BaseLLM
from app.schemas.models import LLMConfig
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.llm.qwen")


class QwenLLM(BaseLLM):
    """通义千问LLM实现"""

    def __init__(self, api_key: str, model: str = "qwen-turbo"):
        self.api_key = api_key
        self.model = model
        dashscope.api_key = api_key

    async def generate(self, prompt: str, config: LLMConfig = None) -> str:
        """同步生成"""
        model = config.model if config else self.model
        temperature = config.temperature if config else 0.7

        response = Generation.call(
            model=model,
            prompt=prompt,
            temperature=temperature,
            result_format="message",
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            logger.error("Qwen生成失败", code=response.code, message=response.message)
            raise Exception(f"Qwen API error: {response.message}")

    async def stream(self, prompt: str, config: LLMConfig = None) -> AsyncIterator[str]:
        """流式生成"""
        model = config.model if config else self.model
        temperature = config.temperature if config else 0.7

        responses = Generation.call(
            model=model,
            prompt=prompt,
            temperature=temperature,
            stream=True,
            incremental_output=True,  # 返回增量内容而非累积内容
            result_format="message",
        )

        for response in responses:
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                if content:
                    yield content
                    # 让出事件循环控制权，允许数据发送到客户端
                    await asyncio.sleep(0)
            else:
                logger.error("Qwen流式生成失败", code=response.code)

    async def generate_chat(self, messages: List[dict], config: LLMConfig = None) -> str:
        """聊天生成"""
        model = config.model if config else self.model
        temperature = config.temperature if config else 0.7

        response = Generation.call(
            model=model,
            messages=messages,
            temperature=temperature,
            result_format="message",
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            logger.error("Qwen聊天生成失败", code=response.code, message=response.message)
            raise Exception(f"Qwen API error: {response.message}")
