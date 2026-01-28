"""ReAct Agent实现"""
import asyncio
import traceback
from typing import AsyncIterator, List, Optional
from dataclasses import dataclass, field

from app.core.llm.base import BaseLLM
from app.core.agent.prompts import REACT_SYSTEM_PROMPT, REACT_STEP_PROMPT, REACT_DIRECT_PROMPT
from app.core.agent.parser import AgentOutputParser, Action, FinalAnswer, ThinkResult
from app.tools.registry import ToolRegistry
from app.schemas.models import AgentEvent, Workflow, WorkflowStep
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.agent.react")

MAX_ITERATIONS = 10  # 最大迭代次数，防止无限循环


@dataclass
class AgentContext:
    """Agent执行上下文"""
    task: str
    workflow: Optional[Workflow] = None
    current_step_index: int = 0
    history: List[dict] = field(default_factory=list)
    iteration: int = 0
    workspace_root: Optional[str] = None


class ReActAgent:
    """ReAct Agent实现思考-行动-观察循环"""

    def __init__(self, llm: BaseLLM, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools
        self.parser = AgentOutputParser()

    async def run(
        self,
        task: str,
        workflow: Optional[Workflow] = None,
        workspace_root: Optional[str] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> AsyncIterator[AgentEvent]:
        """执行任务，返回事件流"""
        logger.info("Agent开始执行", task=task[:50], workspace=workspace_root)

        ctx = AgentContext(task=task, workflow=workflow, workspace_root=workspace_root)

        # 如果有workflow，按步骤执行
        if workflow and workflow.steps:
            for i, step in enumerate(workflow.steps):
                if cancel_event and cancel_event.is_set():
                    yield AgentEvent(type="cancelled", data={"message": "已取消"})
                    return

                ctx.current_step_index = i
                ctx.iteration = 0
                ctx.history = []

                yield AgentEvent(
                    type="step_start",
                    data={"step_index": i, "step": step.model_dump()},
                )

                async for event in self._execute_step(ctx, step, cancel_event):
                    yield event
                    if event.type == "cancelled":
                        return

                yield AgentEvent(type="step_complete", data={"step_index": i})

            yield AgentEvent(
                type="workflow_complete", data={"message": "所有步骤执行完成"}
            )
        else:
            # 直接执行任务
            async for event in self._execute_direct(ctx, cancel_event):
                yield event
                if event.type == "cancelled":
                    return

    async def _execute_step(
        self, ctx: AgentContext, step: WorkflowStep, cancel_event: Optional[asyncio.Event]
    ) -> AsyncIterator[AgentEvent]:
        """执行单个workflow步骤"""
        step_task = f"{ctx.task}\n\n当前步骤: {step.description}"

        while ctx.iteration < MAX_ITERATIONS:
            if cancel_event and cancel_event.is_set():
                yield AgentEvent(type="cancelled", data={"message": "已取消"})
                return

            ctx.iteration += 1

            # 构建prompt
            prompt = self._build_step_prompt(ctx, step)

            # 调用LLM
            try:
                response = await self.llm.generate(prompt)
            except Exception as e:
                logger.error("LLM调用失败", error=str(e))
                yield AgentEvent(type="error", data={"message": str(e)})
                break

            # 解析输出
            result = self.parser.parse(response)

            # 提取并发送思考
            thought = self.parser.extract_thought(response)
            if thought:
                yield AgentEvent(type="thought", data={"content": thought})
                ctx.history.append({"type": "thought", "content": thought})

            if isinstance(result, FinalAnswer):
                yield AgentEvent(
                    type="answer", data={"content": result.content}
                )
                break

            elif isinstance(result, Action):
                yield AgentEvent(
                    type="action",
                    data={"tool": result.tool, "input": result.input},
                )

                # 执行工具
                observation = await self._execute_tool(result, cancel_event)
                yield AgentEvent(type="observation", data={"content": observation})
                if cancel_event and cancel_event.is_set():
                    yield AgentEvent(type="cancelled", data={"message": "已取消"})
                    return

                ctx.history.append(
                    {"type": "action", "tool": result.tool, "input": result.input}
                )
                ctx.history.append({"type": "observation", "content": observation})

            else:
                # 只有思考，继续下一轮
                continue

        if ctx.iteration >= MAX_ITERATIONS:
            yield AgentEvent(
                type="warning",
                data={"message": f"步骤 {step.id} 达到最大迭代次数"},
            )

    async def _execute_direct(
        self, ctx: AgentContext, cancel_event: Optional[asyncio.Event]
    ) -> AsyncIterator[AgentEvent]:
        """直接执行任务（无workflow）"""
        while ctx.iteration < MAX_ITERATIONS:
            if cancel_event and cancel_event.is_set():
                yield AgentEvent(type="cancelled", data={"message": "已取消"})
                return

            ctx.iteration += 1

            prompt = self._build_direct_prompt(ctx)

            try:
                response = await self.llm.generate(prompt)
            except Exception as e:
                logger.error("LLM调用失败", error=str(e))
                yield AgentEvent(type="error", data={"message": str(e)})
                break

            result = self.parser.parse(response)

            thought = self.parser.extract_thought(response)
            if thought:
                yield AgentEvent(type="thought", data={"content": thought})
                ctx.history.append({"type": "thought", "content": thought})

            if isinstance(result, FinalAnswer):
                yield AgentEvent(type="complete", data={"answer": result.content})
                break

            elif isinstance(result, Action):
                yield AgentEvent(
                    type="action",
                    data={"tool": result.tool, "input": result.input},
                )

                observation = await self._execute_tool(result, cancel_event)
                yield AgentEvent(type="observation", data={"content": observation})
                if cancel_event and cancel_event.is_set():
                    yield AgentEvent(type="cancelled", data={"message": "已取消"})
                    return

                ctx.history.append(
                    {"type": "action", "tool": result.tool, "input": result.input}
                )
                ctx.history.append({"type": "observation", "content": observation})

        if ctx.iteration >= MAX_ITERATIONS:
            yield AgentEvent(
                type="complete",
                data={"answer": "达到最大迭代次数，任务可能未完全完成。"},
            )

    async def _execute_tool(
        self, action: Action, cancel_event: Optional[asyncio.Event]
    ) -> str:
        """执行工具并返回观察结果"""
        if action.input.get("__parse_error"):
            raw = action.input.get("__raw_input", "")
            return (
                "输入格式错误: 需要提供有效的JSON对象，键名必须与工具参数名一致。"
                f" 原始输入: {raw}"
            )

        if cancel_event and cancel_event.is_set():
            return "已取消"

        tool = self.tools.get_tool(action.tool)

        if not tool:
            return f"错误: 工具 '{action.tool}' 不存在。可用工具: {[t.name for t in self.tools.get_all_tools()]}"

        try:
            result = await tool.execute(**action.input, cancel_event=cancel_event)
            if result.success:
                return str(result.data) if result.data else "执行成功"
            else:
                return f"执行失败: {result.error}"
        except Exception as e:
            logger.error("工具执行异常", tool=action.tool, input=action.input, error=str(e), tb=traceback.format_exc())
            return f"执行异常: {str(e)}"

    def _build_step_prompt(self, ctx: AgentContext, step: WorkflowStep) -> str:
        """构建步骤执行prompt"""
        tools_desc = self.tools.get_tools_prompt()
        system = REACT_SYSTEM_PROMPT.format(tools_description=tools_desc)

        history_str = self._format_history(ctx.history)
        workspace = ctx.workspace_root or "/tmp"

        step_prompt = REACT_STEP_PROMPT.format(
            workspace_root=workspace,
            task=ctx.task,
            current_step=f"{step.id}. {step.description}",
            history=history_str or "（无历史记录）",
        )

        return f"{system}\n\n{step_prompt}"

    def _build_direct_prompt(self, ctx: AgentContext) -> str:
        """构建直接执行prompt"""
        tools_desc = self.tools.get_tools_prompt()
        system = REACT_SYSTEM_PROMPT.format(tools_description=tools_desc)

        history_str = self._format_history(ctx.history)
        workspace = ctx.workspace_root or "/tmp"

        direct_prompt = REACT_DIRECT_PROMPT.format(
            workspace_root=workspace,
            task=ctx.task,
            history=history_str or "（无历史记录）",
        )

        return f"{system}\n\n{direct_prompt}"

    def _format_history(self, history: List[dict]) -> str:
        """格式化历史记录"""
        lines = []
        for item in history[-10:]:  # 只保留最近10条
            if item["type"] == "thought":
                lines.append(f"思考: {item['content']}")
            elif item["type"] == "action":
                lines.append(f"行动: {item['tool']}")
                lines.append(f"输入: {item['input']}")
            elif item["type"] == "observation":
                lines.append(f"观察: {item['content']}")
        return "\n".join(lines)
