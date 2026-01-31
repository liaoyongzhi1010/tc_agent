"""ReAct Agent实现"""
import asyncio
import os
import traceback
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Callable, Awaitable
from dataclasses import dataclass, field

from app.core.llm.base import BaseLLM
from app.core.agent.prompts import REACT_SYSTEM_PROMPT, REACT_STEP_PROMPT
from app.core.agent.parser import AgentOutputParser, Action, FinalAnswer
from app.core.agent.step_policy import StepPolicy, StepKind
from app.tools.registry import ToolRegistry
from app.schemas.models import AgentEvent, Workflow, WorkflowStep, ToolResult
from app.infrastructure.logger import get_logger
from app.infrastructure.config import settings
from app.infrastructure.workspace import apply_file_ops

logger = get_logger("tc_agent.agent.react")

MAX_ITERATIONS = settings.agent_max_iterations  # 最大迭代次数，防止无限循环


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
    workspace_id: Optional[str] = None
    file_reader: Optional[Callable[[str, str], Awaitable[ToolResult]]] = None
    runner_build_done: bool = False
    runner_full_done: bool = False


class ReActAgent:
    """ReAct Agent实现思考-行动-观察循环"""

    def __init__(self, llm: BaseLLM, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools
        self.parser = AgentOutputParser()
        self.step_policy = StepPolicy()

    async def run(
        self,
        task: str,
        workflow: Optional[Workflow] = None,
        workspace_root: Optional[str] = None,
        file_reader: Optional[Callable[[str, str], Awaitable[ToolResult]]] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> AsyncIterator[AgentEvent]:
        """执行任务，返回事件流"""
        logger.info("Agent开始执行", task=task[:50], workspace=workspace_root)

        ctx = AgentContext(
            task=task,
            workflow=workflow,
            workspace_root=workspace_root,
            workspace_id=workflow.workspace_id if workflow else None,
            file_reader=file_reader,
        )

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

            step_kind = self.step_policy.classify(step.description)
            if step_kind == StepKind.GENERATE and not self._has_tool("ta_generator"):
                step_kind = StepKind.GENERIC
            if step_kind == StepKind.GENERATE:
                async for event in self._auto_generate(ctx, step, cancel_event):
                    yield event
                    if event.type == "cancelled":
                        return
            elif step_kind in (StepKind.BUILD, StepKind.RUN):
                async for event in self._auto_run_runner(ctx, step, step_kind, cancel_event):
                    yield event
                    if event.type == "cancelled":
                        return
            else:
                async for event in self._execute_step(ctx, step, step_kind, cancel_event):
                    yield event
                    if event.type == "cancelled":
                        return

            yield AgentEvent(type="step_complete", data={"step_index": i})

        yield AgentEvent(
            type="workflow_complete", data={"message": "所有步骤执行完成"}
        )

    async def _execute_step(
        self,
        ctx: AgentContext,
        step: WorkflowStep,
        step_kind: StepKind,
        cancel_event: Optional[asyncio.Event],
    ) -> AsyncIterator[AgentEvent]:
        """执行单个workflow步骤"""

        while ctx.iteration < MAX_ITERATIONS:
            if cancel_event and cancel_event.is_set():
                yield AgentEvent(type="cancelled", data={"message": "已取消"})
                return

            ctx.iteration += 1

            # 构建prompt
            prompt = self._build_step_prompt(ctx, step, step_kind)

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
                allowed = set(self.step_policy.allowed_tools(step_kind))
                if allowed and result.tool not in allowed:
                    message = f"本步骤只允许工具: {', '.join(sorted(allowed))}"
                    yield AgentEvent(type="observation", data={"content": message})
                    ctx.history.append({"type": "observation", "content": message})
                    return
                yield AgentEvent(
                    type="action",
                    data={"tool": result.tool, "input": normalized_input},
                )

                # 执行工具
                observation, file_ops, success = await self._execute_tool(
                    result.tool, normalized_input, ctx, cancel_event
                )
                if file_ops:
                    yield AgentEvent(type="file_ops", data={"ops": file_ops})
                obs_data = {"content": observation, "tool": result.tool}
                if success is not None:
                    obs_data["success"] = success
                yield AgentEvent(type="observation", data=obs_data)
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

    async def _auto_generate(
        self,
        ctx: AgentContext,
        step: WorkflowStep,
        cancel_event: Optional[asyncio.Event],
    ) -> AsyncIterator[AgentEvent]:
        if ctx.ta_dir and ctx.ca_dir:
            yield AgentEvent(type="observation", data={"content": "已存在 TA/CA 目录，跳过生成。"})
            return
        name = ctx.project_name or self._guess_project_name(ctx.task)
        ctx.project_name = name

        if not ctx.ta_dir:
            ta_input = self._normalize_tool_input(
                "ta_generator",
                {"name": name, "output_dir": ctx.workspace_root, "overwrite": True},
                ctx,
            )
            yield AgentEvent(type="action", data={"tool": "ta_generator", "input": ta_input})
            obs, file_ops, success = await self._execute_tool("ta_generator", ta_input, ctx, cancel_event)
            if file_ops:
                yield AgentEvent(type="file_ops", data={"ops": file_ops})
            obs_data = {"content": obs, "tool": "ta_generator"}
            if success is not None:
                obs_data["success"] = success
            yield AgentEvent(type="observation", data=obs_data)

        if not ctx.ca_dir:
            ca_input = self._normalize_tool_input(
                "ca_generator",
                {"name": name, "ta_name": name, "output_dir": ctx.workspace_root, "overwrite": True},
                ctx,
            )
            yield AgentEvent(type="action", data={"tool": "ca_generator", "input": ca_input})
            obs, file_ops, success = await self._execute_tool("ca_generator", ca_input, ctx, cancel_event)
            if file_ops:
                yield AgentEvent(type="file_ops", data={"ops": file_ops})
            obs_data = {"content": obs, "tool": "ca_generator"}
            if success is not None:
                obs_data["success"] = success
            yield AgentEvent(type="observation", data=obs_data)

    async def _auto_run_runner(
        self,
        ctx: AgentContext,
        step: WorkflowStep,
        step_kind: StepKind,
        cancel_event: Optional[asyncio.Event],
    ) -> AsyncIterator[AgentEvent]:
        if not self._has_tool("optee_runner"):
            yield AgentEvent(type="observation", data={"content": "optee_runner 不可用，跳过编译/运行。"})
            return
        if not ctx.ta_dir or not ctx.ca_dir:
            yield AgentEvent(type="observation", data={"content": "缺少 TA/CA 目录，无法运行。"})
            return

        if step_kind == StepKind.BUILD and ctx.runner_build_done:
            yield AgentEvent(type="observation", data={"content": "已编译，跳过重复编译。"})
            return
        if step_kind == StepKind.RUN and ctx.runner_full_done:
            yield AgentEvent(type="observation", data={"content": "已完成运行验证，跳过重复运行。"})
            return

        mode = self.step_policy.runner_mode(step_kind, ctx.runner_build_done) or "full"
        input_payload = {
            "workspace_id": ctx.workspace_id,
            "ta_dir": ctx.ta_dir,
            "ca_dir": ctx.ca_dir,
            "mode": mode,
        }
        runner_input = self._normalize_tool_input("optee_runner", input_payload, ctx)
        yield AgentEvent(type="action", data={"tool": "optee_runner", "input": runner_input})
        obs, file_ops, success = await self._execute_tool("optee_runner", runner_input, ctx, cancel_event)
        if file_ops:
            yield AgentEvent(type="file_ops", data={"ops": file_ops})
        obs_data = {"content": obs, "tool": "optee_runner"}
        if success is not None:
            obs_data["success"] = success
        yield AgentEvent(type="observation", data=obs_data)

    def _normalize_tool_input(
        self,
        tool: str,
        tool_input: Dict[str, Any],
        ctx: AgentContext,
    ) -> Dict[str, Any]:
        workspace_root = ctx.workspace_root
        if not workspace_root or not isinstance(tool_input, dict):
            return tool_input

        if tool in ("file_read", "file_write", "crypto_helper"):
            return tool_input

        if tool in ("ta_generator", "ca_generator"):
            normalized = dict(tool_input)
            def _normalize_name(name: Optional[str]) -> Optional[str]:
                if not name:
                    return name
                for suffix in ("_ta", "_ca"):
                    if name.endswith(suffix):
                        name = name[: -len(suffix)]
                return name

            def _normalize_output_dir(path: Optional[str], name: Optional[str]) -> str:
                if not path:
                    return workspace_root
                try:
                    p = Path(path)
                except Exception:
                    return workspace_root
                base = p.name
                name_base = name or ""
                if base in {name_base, f"{name_base}_ta", f"{name_base}_ca"} or base.endswith(("_ta", "_ca")):
                    if workspace_root and Path(workspace_root) in p.parents:
                        return workspace_root
                return path

            normalized["output_dir"] = _normalize_output_dir(
                normalized.get("output_dir"), normalized.get("name")
            )

            if tool == "ta_generator":
                name = _normalize_name(normalized.get("name"))
                if name:
                    normalized["name"] = name
                if ctx.project_name and name and name != ctx.project_name:
                    normalized["name"] = ctx.project_name
                elif name and not ctx.project_name:
                    ctx.project_name = name
            if tool == "ca_generator":
                name = _normalize_name(normalized.get("name"))
                ta_name = _normalize_name(normalized.get("ta_name"))
                if name:
                    normalized["name"] = name
                if ta_name:
                    normalized["ta_name"] = ta_name
                if ctx.project_name:
                    if name and name != ctx.project_name:
                        normalized["name"] = ctx.project_name
                    if ta_name and ta_name != ctx.project_name:
                        normalized["ta_name"] = ctx.project_name
                elif name:
                    ctx.project_name = name
                elif ta_name:
                    ctx.project_name = ta_name

            return normalized

        if tool == "optee_runner":
            normalized = dict(tool_input)
            if ctx.workspace_id:
                normalized["workspace_id"] = ctx.workspace_id
            if ctx.ta_dir and not normalized.get("ta_dir"):
                normalized["ta_dir"] = ctx.ta_dir
            if ctx.ca_dir and not normalized.get("ca_dir"):
                normalized["ca_dir"] = ctx.ca_dir

            def _rel_if_under_workspace(path: Optional[str]) -> Optional[str]:
                if not path or not ctx.workspace_root:
                    return path
                try:
                    if os.path.isabs(path):
                        rel = os.path.relpath(path, ctx.workspace_root)
                        if not rel.startswith(".."):
                            return rel
                except Exception:
                    return path
                return path

            normalized["ta_dir"] = _rel_if_under_workspace(normalized.get("ta_dir"))
            normalized["ca_dir"] = _rel_if_under_workspace(normalized.get("ca_dir"))
            normalized["ca_bin"] = _rel_if_under_workspace(normalized.get("ca_bin"))
            return normalized

        return tool_input

    def _guess_project_name(self, task: str) -> str:
        text = task or ""
        if "HELLO" in text.upper():
            return "hello"
        for token in text.replace("，", " ").replace(",", " ").split():
            if token.isidentifier():
                return token.lower()
        return "ta_app"

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        ctx: AgentContext,
        cancel_event: Optional[asyncio.Event],
    ) -> Tuple[str, Optional[List[Dict[str, Any]]], Optional[bool]]:
        """执行工具并返回观察结果"""
        if tool_input.get("__parse_error"):
            raw = tool_input.get("__raw_input", "")
            return (
                "输入格式错误: 需要提供有效的JSON对象，键名必须与工具参数名一致。"
                f" 原始输入: {raw}"
            ), None, False

        if cancel_event and cancel_event.is_set():
            return "已取消", None, False

        tool = self.tools.get_tool(tool_name)

        if not tool:
            return (
                f"错误: 工具 '{tool_name}' 不存在。可用工具: {[t.name for t in self.tools.get_all_tools()]}",
                None,
                False,
            )

        try:
            if tool_name == "file_read":
                if not ctx.file_reader:
                    return "执行失败: file_read 仅支持前端执行", None, False
                path = tool_input.get("path") if isinstance(tool_input, dict) else None
                encoding = tool_input.get("encoding", "utf-8") if isinstance(tool_input, dict) else "utf-8"
                if not path:
                    return "执行失败: 缺少path", None, False
                result = await ctx.file_reader(path, encoding)
                if result.success:
                    return str(result.data) if result.data else "执行成功", None, True
                return f"执行失败: {result.error}", None, False

            if tool_name == "file_write":
                path = tool_input.get("path")
                content = tool_input.get("content", "")
                if path and path.endswith("_ta.c"):
                    if "TA_InvokeCommandEntryPoint" not in content or "TA_CreateEntryPoint" not in content:
                        return "拒绝写入：TA 源文件必须保留 OP-TEE 入口函数。", None, False
                file_ops = [
                    {
                        "path": tool_input.get("path"),
                        "content": tool_input.get("content", ""),
                        "encoding": tool_input.get("encoding", "utf-8"),
                        "create_dirs": tool_input.get("create_dirs", True),
                    }
                ]
                if ctx.workspace_id:
                    apply_file_ops(ctx.workspace_id, ctx.workspace_root or "", file_ops)
                return f"已提交文件写入（前端执行）：{tool_input.get('path')}", file_ops, True

            if tool_name in ("ta_generator", "ca_generator"):
                tool_input = {**tool_input, "emit_files": True}

            result = await tool.execute(**tool_input, cancel_event=cancel_event)
            file_ops: Optional[List[Dict[str, Any]]] = None
            if result.success and isinstance(result.data, dict):
                file_ops = result.data.pop("file_ops", None)
                if tool_name == "ta_generator":
                    output_dir = result.data.get("output_dir")
                    if output_dir:
                        ctx.ta_dir = output_dir
                if tool_name == "ca_generator":
                    output_dir = result.data.get("output_dir")
                    if output_dir:
                        ctx.ca_dir = output_dir
                if tool_name == "optee_runner":
                    mode = tool_input.get("mode")
                    if mode == "build":
                        ctx.runner_build_done = True
                    elif mode == "test":
                        ctx.runner_full_done = True
                    elif mode == "full":
                        ctx.runner_build_done = True
                        ctx.runner_full_done = True
            if result.success:
                if file_ops and ctx.workspace_id:
                    apply_file_ops(ctx.workspace_id, ctx.workspace_root or "", file_ops)
                if tool_name == "optee_runner" and isinstance(result.data, dict):
                    log = result.data.get("log")
                    if log:
                        return f"执行成功\n日志:\n{log}", file_ops, True
                return (str(result.data) if result.data else "执行成功"), file_ops, True
            else:
                details: List[str] = []
                if isinstance(result.data, dict):
                    log = result.data.get("log")
                    if log:
                        details.append(f"日志:\n{log}")
                    exit_code = result.data.get("exit_code")
                    if exit_code is not None:
                        details.append(f"退出码: {exit_code}")
                message = f"执行失败: {result.error}" if result.error else "执行失败"
                if details:
                    message += "\n" + "\n".join(details)
                return message, None, False
        except Exception as e:
            logger.error("工具执行异常", tool=tool_name, input=tool_input, error=str(e), tb=traceback.format_exc())
            return f"执行异常: {str(e)}", None, False

    def _build_step_prompt(self, ctx: AgentContext, step: WorkflowStep, step_kind: StepKind) -> str:
        """构建步骤执行prompt"""
        tools_desc = self.tools.get_tools_prompt()
        system = REACT_SYSTEM_PROMPT.format(tools_description=tools_desc)

        history_str = self._format_history(ctx.history)
        workspace = ctx.workspace_root or "/tmp"
        ta_dir = ctx.ta_dir or "（未生成）"
        ca_dir = ctx.ca_dir or "（未生成）"
        allowed_tools = self.step_policy.allowed_tools(step_kind)
        allowed_text = ", ".join(allowed_tools) if allowed_tools else "（无）"
        extra_context = "实现步骤优先修改 TA 的 process_command，保留 TA 入口函数。" if step_kind == StepKind.IMPLEMENT else "（无）"

        step_prompt = REACT_STEP_PROMPT.format(
            workspace_root=workspace,
            task=ctx.task,
            current_step=f"{step.id}. {step.description}",
            ta_dir=ta_dir,
            ca_dir=ca_dir,
            allowed_tools=allowed_text,
            history=history_str or "（无历史记录）",
            extra_context=extra_context,
        )

        return f"{system}\n\n{step_prompt}"

    def _has_tool(self, name: str) -> bool:
        return self.tools.get_tool(name) is not None

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
