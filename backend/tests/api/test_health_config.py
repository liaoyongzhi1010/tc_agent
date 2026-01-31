"""基础健康检查与配置接口测试。"""


def test_health(app_client):
    resp = app_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_config(app_client):
    resp = app_client.get("/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm_provider" in data
    assert "embedding_model" in data
