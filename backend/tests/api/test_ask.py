"""Ask 模式（RAG 流式问答）测试。"""
import json

from app.api import ask as ask_module
from app.core.llm import LLMFactory


class DummyDoc:
    def __init__(self, content: str, metadata: dict, score: float = 0.5) -> None:
        self.content = content
        self.metadata = metadata
        self.score = score


class DummyRetriever:
    def __init__(self, docs=None) -> None:
        self._docs = docs or []

    async def retrieve(self, query: str, top_k: int = 5, where: dict | None = None):
        return self._docs


class DummyLLM:
    async def stream(self, prompt: str):
        # 简化的流式输出
        yield "测试"
        yield "回答"


def test_ask_stream_basic(app_client, dummy_vector_store, monkeypatch):
    # 构造检索结果
    docs = [
        DummyDoc(content="参考内容A", metadata={"source": "docA.md"}, score=0.9),
        DummyDoc(content="参考内容B", metadata={"source": "docB.md"}, score=0.8),
    ]
    dummy_vector_store.retriever = DummyRetriever(docs)

    async def _get_vector_store():
        return dummy_vector_store

    monkeypatch.setattr(ask_module, "get_vector_store", _get_vector_store)
    monkeypatch.setattr(LLMFactory, "create_from_config", lambda: DummyLLM())

    resp = app_client.post("/ask/stream", json={"query": "什么是OP-TEE？"})
    assert resp.status_code == 200

    body = resp.text
    # 至少包含：检索状态 / 来源 / 内容 / 完成标记
    assert '"type": "status"' in body
    assert '"type": "sources"' in body
    assert '"type": "content"' in body
    assert '"type": "done"' in body

    # 来源中应包含文档 source
    assert "docA.md" in body
    assert "docB.md" in body
