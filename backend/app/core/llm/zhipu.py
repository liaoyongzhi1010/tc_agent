"""智谱GLM LLM"""
import asyncio
import threading
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

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        return response.choices[0].message.content

    async def stream(self, prompt: str, config: LLMConfig = None) -> AsyncIterator[str]:
        """流式生成"""
        model = config.model if config else self.model
        temperature = config.temperature if config else 0.7
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _worker() -> None:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    stream=True,
                )
                for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        loop.call_soon_threadsafe(queue.put_nowait, content)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    async def generate_chat(self, messages: List[dict], config: LLMConfig = None) -> str:
        """聊天生成"""
        model = config.model if config else self.model
        temperature = config.temperature if config else 0.7

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=model,
            messages=messages,
            temperature=temperature,
        )

        return response.choices[0].message.content
