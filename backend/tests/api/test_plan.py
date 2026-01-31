"""Plan 接口测试：初始化 / 修改 / 确认。"""
import uuid

from app.api import plan as plan_module
from app.infrastructure.workflow_store import MemoryWorkflowStore
from app.schemas.models import Workflow, WorkflowStep


class DummyWorkflowManager:
    async def generate_workflow(self, task: str, context: str | None):
        return Workflow(
            id=str(uuid.uuid4()),
            task=task,
            steps=[WorkflowStep(id="1", description="生成代码框架")],
        )

    async def refine_workflow(self, workflow: Workflow, instruction: str):
        workflow.steps.append(WorkflowStep(id="2", description=f"根据指令: {instruction}"))
        return workflow


def test_plan_flow(app_client, monkeypatch):
    # 替换工作流管理器与存储
    store = MemoryWorkflowStore()

    async def _get_manager():
        return DummyWorkflowManager()

    monkeypatch.setattr(plan_module, "get_workflow_manager", _get_manager)
    monkeypatch.setattr(plan_module, "get_workflow_store", lambda: store)

    # init
    resp = app_client.post("/plan/init", json={"task": "创建TA"})
    assert resp.status_code == 200
    data = resp.json()
    workflow_id = data["workflow_id"]
    assert data["steps"]

    # refine
    resp = app_client.post(
        "/plan/refine",
        json={"workflow_id": workflow_id, "instruction": "增加日志"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["steps"]) >= 2

    # confirm
    resp = app_client.post("/plan/confirm", json={"workflow_id": workflow_id})
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
