"""测试公共夹具与桩对象（避免真实网络/模型加载）。"""
from __future__ import annotations

from typing import Any, List

import sys
from pathlib import Path

# 确保 tests 能导入 backend/app
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient


class DummyDoc:
    """简化的检索结果对象"""

    def __init__(self, content: str, metadata: dict, score: float = 0.5) -> None:
        self.content = content
        self.metadata = metadata
        self.score = score


class DummyRetriever:
    """可控的检索器（测试中按需注入结果）"""

    def __init__(self, docs: List[DummyDoc] | None = None) -> None:
        self._docs = docs or []

    async def retrieve(self, query: str, top_k: int = 5, where: dict | None = None):
        return self._docs


class DummyVectorStore:
    """简化向量库桩实现"""

    def __init__(self, retriever: DummyRetriever | None = None) -> None:
        self.retriever = retriever or DummyRetriever()
        self.added: list[tuple[str, list[str], list[dict]]] = []

    def get_retriever(self, collection_type: str = "all"):
        return self.retriever

    async def add_documents(self, collection: str, documents: list[str], metadatas: list[dict]) -> None:
        self.added.append((collection, documents, metadatas))

    async def load_preset_knowledge(self) -> None:
        return None

    async def get_stats(self) -> dict:
        return {"text": {"name": "text", "count": 0}, "code": {"name": "code", "count": 0}}


@pytest.fixture
def dummy_vector_store():
    """默认向量库桩"""
    return DummyVectorStore()


@pytest.fixture
def app_client(monkeypatch, dummy_vector_store):
    """FastAPI TestClient（屏蔽真实向量库初始化）"""
    async def _get_vector_store():
        return dummy_vector_store

    # 主模块里导入的是局部引用，需要双重打桩
    import app.infrastructure.vector_store as vector_store_module
    import app.main as main_module

    monkeypatch.setattr(vector_store_module, "get_vector_store", _get_vector_store)
    monkeypatch.setattr(main_module, "get_vector_store", _get_vector_store)

    from app.main import app

    return TestClient(app)

