"""ReAct Agent 文件写入闭环测试（file_write -> 后端工作区落盘）。"""
from pathlib import Path

import pytest

from app.core.agent.react_agent import ReActAgent
from app.schemas.models import Workflow, WorkflowStep
from app.tools.registry import ToolRegistry
from app.tools.common.file import FileWriteTool
import app.infrastructure.workspace as workspace_module


class DummyLLM:
    """按顺序返回预设输出的 LLM 桩"""

    def __init__(self) -> None:
        self._count = 0

    async def generate(self, prompt: str) -> str:
        self._count += 1
        if self._count == 1:
            return (
                "思考: 写一个文件\n"
                "行动: file_write\n"
                "输入: {\"path\": \"demo.txt\", \"content\": \"hello\"}\n"
            )
        return "思考: 完成\n最终答案: ok"


@pytest.mark.asyncio
async def test_agent_file_write_to_backend_workspace(tmp_path, monkeypatch):
    # 设置后端工作区根目录
    monkeypatch.setattr(workspace_module, "WORKSPACE_ROOT", tmp_path)

    # 创建后端工作区目录
    workspace_id = "ws1"
    (tmp_path / workspace_id).mkdir(parents=True, exist_ok=True)

    # 构造 workflow
    workflow = Workflow(
        id="wf1",
        task="写文件",
        steps=[WorkflowStep(id="1", description="生成文件")],
        workspace_root=str(tmp_path),  # 模拟前端工作区
        workspace_id=workspace_id,
        status="confirmed",
    )

    tools = ToolRegistry()
    tools.register(FileWriteTool(), "core")
    agent = ReActAgent(DummyLLM(), tools)

    async for _ in agent.run(workflow.task, workflow, workflow.workspace_root):
        pass

    # 后端工作区应落盘
    target = Path(tmp_path) / workspace_id / "demo.txt"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello"
