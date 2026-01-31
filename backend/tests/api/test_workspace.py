"""工作区 API 测试（初始化 + 同步文件）。"""
from pathlib import Path

import app.infrastructure.workspace as workspace_module


def test_workspace_init_and_sync(app_client, tmp_path, monkeypatch):
    # 指向临时目录，避免污染真实环境
    monkeypatch.setattr(workspace_module, "WORKSPACE_ROOT", tmp_path)

    # init
    resp = app_client.post("/workspace/init")
    assert resp.status_code == 200
    workspace_id = resp.json()["workspace_id"]

    # sync
    payload = {
        "workspace_id": workspace_id,
        "files": [
            {"path": "demo/hello.txt", "content": "hello", "encoding": "utf-8"},
        ],
    }
    resp = app_client.post("/workspace/sync", json=payload)
    assert resp.status_code == 200

    # 文件应写入到后端工作区
    file_path = Path(tmp_path) / workspace_id / "demo" / "hello.txt"
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == "hello"
