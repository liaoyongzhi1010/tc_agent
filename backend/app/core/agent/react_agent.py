"""ReAct Agent实现"""
import asyncio
import traceback
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional
from dataclasses import dataclass, field

from app.core.llm.base import BaseLLM
from app.core.agent.prompts import REACT_SYSTEM_PROMPT, REACT_STEP_PROMPT
from app.core.agent.parser import AgentOutputParser, Action, FinalAnswer
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
    project_name: Optional[str] = None
    ta_dir: Optional[str] = None
    ca_dir: Optional[str] = None


class ReActAgent:
    """ReAct Agent实现思考-行动-观察循环"""

    def __init__(self, llm: BaseLLM, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools
        self.parser = AgentOutputParser()

    def _ensure_workspace_writable(self, workspace_root: Optional[str]) -> Optional[str]:
        if not workspace_root:
            return "缺少工作区路径，请先打开一个工作区文件夹"

        try:
            root = Path(workspace_root).expanduser().resolve()
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".tc_agent_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return None
        except Exception as exc:
            return f"工作区不可写: {workspace_root} ({exc})"

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

        workspace_error = self._ensure_workspace_writable(ctx.workspace_root)
        if workspace_error:
            yield AgentEvent(type="error", data={"message": workspace_error})
            return

        if not workflow or not workflow.steps:
            yield AgentEvent(type="error", data={"message": "缺少工作流，无法执行"})
            return

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
                normalized_input = self._normalize_tool_input(
                    result.tool, result.input, ctx
                )
                if result.tool in ("ta_generator", "ca_generator"):
                    skip_message = self._maybe_skip_generator(result.tool, ctx)
                    if skip_message:
                        yield AgentEvent(
                            type="observation",
                            data={"content": skip_message},
                        )
                        ctx.history.append({"type": "observation", "content": skip_message})
                        continue
                    if self._already_attempted_tool(ctx.history, result.tool):
                        message = (
                            f"{result.tool} 已在本步骤尝试过，若失败请检查工作区权限或手动修复后重试。"
                        )
                        yield AgentEvent(type="observation", data={"content": message})
                        ctx.history.append({"type": "observation", "content": message})
                        continue
                yield AgentEvent(
                    type="action",
                    data={"tool": result.tool, "input": normalized_input},
                )

                # 执行工具
                observation = await self._execute_tool(
                    result.tool, normalized_input, ctx, cancel_event
                )
                yield AgentEvent(type="observation", data={"content": observation})
                if cancel_event and cancel_event.is_set():
                    yield AgentEvent(type="cancelled", data={"message": "已取消"})
                    return

                ctx.history.append(
                    {"type": "action", "tool": result.tool, "input": normalized_input}
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

    def _normalize_tool_input(
        self,
        tool: str,
        tool_input: Dict[str, Any],
        ctx: AgentContext,
    ) -> Dict[str, Any]:
        workspace_root = ctx.workspace_root
        if not workspace_root or not isinstance(tool_input, dict):
            return tool_input

        root = Path(workspace_root).expanduser().resolve()
        normalized = dict(tool_input)
        dir_keys = {"output_dir", "source_dir", "ta_dir", "ca_dir", "cwd"}
        file_keys = {"path", "ta_path", "ca_file"}

        def coerce_path(value: str, is_dir: bool) -> str:
            try:
                path = Path(value).expanduser()
                if not path.is_absolute():
                    path = (root / path).resolve()
                else:
                    resolved = path.resolve()
                    try:
                        is_inside = resolved.is_relative_to(root)
                    except AttributeError:
                        is_inside = resolved == root or root in resolved.parents
                    if not is_inside:
                        if is_dir:
                            return str((root / resolved.name).resolve())
                        return str((root / resolved.name).resolve())
                return str(path)
            except Exception:
                return value

        for key in dir_keys:
            value = normalized.get(key)
            if isinstance(value, str):
                new_value = coerce_path(value, is_dir=True)
                if new_value != value:
                    logger.warning("路径已重写为工作区内", tool=tool, key=key, src=value, dest=new_value)
                    normalized[key] = new_value

        for key in file_keys:
            value = normalized.get(key)
            if isinstance(value, str):
                new_value = coerce_path(value, is_dir=False)
                if new_value != value:
                    logger.warning("路径已重写为工作区内", tool=tool, key=key, src=value, dest=new_value)
                    normalized[key] = new_value

        if tool in ("ta_generator", "ca_generator"):
            if "output_dir" not in normalized or not normalized.get("output_dir"):
                normalized["output_dir"] = str(root)

            if tool == "ta_generator":
                name = normalized.get("name")
                if ctx.project_name and name and name != ctx.project_name:
                    normalized["name"] = ctx.project_name
                elif name and not ctx.project_name:
                    ctx.project_name = name
            if tool == "ca_generator":
                name = normalized.get("name")
                ta_name = normalized.get("ta_name")
                if ctx.project_name:
                    if name and name != ctx.project_name:
                        normalized["name"] = ctx.project_name
                    if ta_name and ta_name != ctx.project_name:
                        normalized["ta_name"] = ctx.project_name
                elif name:
                    ctx.project_name = name
                elif ta_name:
                    ctx.project_name = ta_name

        if tool == "workflow_runner":
            if ctx.ta_dir and not normalized.get("ta_dir"):
                normalized["ta_dir"] = ctx.ta_dir
            if ctx.ca_dir and (
                not normalized.get("ca_dir") or normalized.get("ca_dir") == str(root)
            ):
                normalized["ca_dir"] = ctx.ca_dir

        if tool == "docker_build":
            build_type = normalized.get("build_type")
            if build_type == "ta" and ctx.ta_dir and not normalized.get("source_dir"):
                normalized["source_dir"] = ctx.ta_dir
            if build_type == "ca" and ctx.ca_dir and not normalized.get("source_dir"):
                normalized["source_dir"] = ctx.ca_dir

        return normalized

    def _already_attempted_tool(self, history: List[dict], tool_name: str) -> bool:
        for item in history:
            if item.get("type") == "action" and item.get("tool") == tool_name:
                return True
        return False

    def _maybe_skip_generator(self, tool_name: str, ctx: AgentContext) -> Optional[str]:
        if tool_name == "ta_generator" and ctx.ta_dir:
            return f"TA 已生成在 {ctx.ta_dir}，跳过重复生成。"
        if tool_name == "ca_generator" and ctx.ca_dir:
            return f"CA 已生成在 {ctx.ca_dir}，跳过重复生成。"
        return None

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        ctx: AgentContext,
        cancel_event: Optional[asyncio.Event],
    ) -> str:
        """执行工具并返回观察结果"""
        if tool_input.get("__parse_error"):
            raw = tool_input.get("__raw_input", "")
            return (
                "输入格式错误: 需要提供有效的JSON对象，键名必须与工具参数名一致。"
                f" 原始输入: {raw}"
            )

        if cancel_event and cancel_event.is_set():
            return "已取消"

        tool = self.tools.get_tool(tool_name)

        if not tool:
            return f"错误: 工具 '{tool_name}' 不存在。可用工具: {[t.name for t in self.tools.get_all_tools()]}"

        try:
            result = await tool.execute(**tool_input, cancel_event=cancel_event)
            if result.success and isinstance(result.data, dict):
                if tool_name == "ta_generator":
                    output_dir = result.data.get("output_dir")
                    if output_dir:
                        ctx.ta_dir = output_dir
                if tool_name == "ca_generator":
                    output_dir = result.data.get("output_dir")
                    if output_dir:
                        ctx.ca_dir = output_dir
            if result.success:
                return str(result.data) if result.data else "执行成功"
            else:
                return f"执行失败: {result.error}"
        except Exception as e:
            logger.error("工具执行异常", tool=tool_name, input=tool_input, error=str(e), tb=traceback.format_exc())
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
