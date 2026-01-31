"""Code 执行接口基础测试（workflow 不存在时返回错误）。"""
from app.api import code as code_module
from app.infrastructure.workflow_store import MemoryWorkflowStore


def test_code_ws_workflow_not_found(app_client, monkeypatch):
    # 确保使用空的内存存储
    monkeypatch.setattr(code_module, "get_workflow_store", lambda: MemoryWorkflowStore())

    with app_client.websocket_connect("/code/execute/does-not-exist") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
