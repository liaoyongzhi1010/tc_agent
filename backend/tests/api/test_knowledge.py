"""知识库 API 测试（添加文档）。"""

from app.api import knowledge as knowledge_module


def test_add_document(app_client, dummy_vector_store, monkeypatch):
    async def _get_vector_store():
        return dummy_vector_store

    monkeypatch.setattr(knowledge_module, "get_vector_store", _get_vector_store)

    payload = {
        "content": "测试文档内容",
        "collection": "text",
        "metadata": {"source": "test.md"},
    }
    resp = app_client.post("/knowledge/add-document", json=payload)
    assert resp.status_code == 200

    # 校验向量库收到内容
    assert dummy_vector_store.added
    collection, docs, metas = dummy_vector_store.added[-1]
    assert collection == "text"
    assert docs == ["测试文档内容"]
    assert metas[0]["source"] == "test.md"
