"""Workflow管理器"""
import json
import re
import uuid
from typing import List, Optional

from app.core.llm.base import BaseLLM
from app.core.rag.base import BaseRetriever
from app.core.workflow.prompts import WORKFLOW_GENERATION_PROMPT, WORKFLOW_REFINE_PROMPT
from app.schemas.models import Workflow, WorkflowStep
from app.infrastructure.logger import get_logger

logger = get_logger("tc_agent.workflow.manager")


class WorkflowManager:
    """Workflow管理器，负责生成和修改工作流程"""

    def __init__(self, llm: BaseLLM, retriever: Optional[BaseRetriever] = None):
        self.llm = llm
        self.retriever = retriever

    async def generate_workflow(
        self, task: str, context: Optional[str] = None
    ) -> Workflow:
        """生成工作流程"""
        logger.info("生成workflow", task=task[:50])

        # RAG检索相关知识
        rag_context = context or ""
        if self.retriever and not context:
            try:
                docs = await self.retriever.retrieve(
                    task, top_k=3, where={"scope": "plan"}
                )
                if docs:
                    rag_context = "\n\n---\n\n".join(
                        [
                            f"[{d.metadata.get('source', 'unknown')}]\n{d.content}"
                            for d in docs
                        ]
                    )
            except Exception as e:
                logger.warning("RAG检索失败", error=str(e))
                rag_context = "（未找到相关参考资料）"

        if not rag_context:
            rag_context = "（未找到相关参考资料）"

        # 构建prompt并生成
        prompt = WORKFLOW_GENERATION_PROMPT.format(task=task, context=rag_context)

        try:
            response = await self.llm.generate(prompt)
            steps = self._parse_workflow_response(response, task)
        except Exception as e:
            logger.error("LLM生成失败", error=str(e))
            # 返回默认workflow
            steps = self._get_default_steps(task)

        workflow = Workflow(
            id=str(uuid.uuid4()),
            task=task,
            steps=steps,
            status="draft",
        )

        logger.info("workflow生成完成", workflow_id=workflow.id, steps_count=len(steps))
        return workflow

    async def refine_workflow(self, workflow: Workflow, instruction: str) -> Workflow:
        """根据指令修改工作流程"""
        logger.info("修改workflow", workflow_id=workflow.id, instruction=instruction[:50])

        # 构建当前步骤描述
        current_steps = "\n".join(
            [f"{s.id}. {s.description}" for s in workflow.steps]
        )

        prompt = WORKFLOW_REFINE_PROMPT.format(
            task=workflow.task,
            current_steps=current_steps,
            instruction=instruction,
        )

        try:
            response = await self.llm.generate(prompt)
            new_steps = self._parse_workflow_response(response, workflow.task)
            workflow.steps = new_steps
        except Exception as e:
            logger.error("修改workflow失败", error=str(e))
            # 保持原样

        return workflow

    def _parse_workflow_response(self, response: str, task: str) -> List[WorkflowStep]:
        """解析LLM返回的workflow"""
        try:
            def _need_run_verify(text: str) -> bool:
                keywords = ("运行", "QEMU", "验证", "测试", "执行")
                return any(k.lower() in text.lower() for k in keywords)

            def _build_desc(item: dict) -> str:
                desc = (item.get("description") or "").strip()
                if desc:
                    return desc
                return (item.get("details") or "").strip()

            # 尝试提取JSON块
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析
                json_str = response.strip()

            data = json.loads(json_str)
            steps = []
            for item in data.get("steps", []):
                description = _build_desc(item)
                step = WorkflowStep(
                    id=str(item.get("id", len(steps) + 1)),
                    description=description,
                    status="pending",
                )
                steps.append(step)

            run_verify = _need_run_verify(task or "")
            if not steps or len(steps) < 3:
                raise ValueError("No steps parsed")

            if run_verify and len(steps) >= 4:
                last = steps[-1].description or ""
                prev = steps[-2].description or ""
                if ("验证" in last and "运行" in prev) or ("验证" in last and "QEMU" in prev):
                    steps = steps[:-1]

            if len(steps) >= 2:
                first = steps[0].description or ""
                second = steps[1].description or ""
                if ("创建" in first and "目录" in first) and ("生成" in second and "模板" in second):
                    steps = [WorkflowStep(id="1", description="生成TA/CA模板")] + steps[2:]
                    for idx, step in enumerate(steps, start=1):
                        step.id = str(idx)

            return steps

        except Exception as e:
            logger.warning("解析workflow失败，使用默认", error=str(e))
            return self._get_default_steps(task)

    def _get_default_steps(self, task: str) -> List[WorkflowStep]:
        """返回默认工作流步骤（保证>=3步）"""
        def _need_run_verify(text: str) -> bool:
            keywords = ("运行", "QEMU", "验证", "测试", "执行")
            return any(k.lower() in text.lower() for k in keywords)

        run_verify = _need_run_verify(task or "")
        if run_verify:
            return [
                WorkflowStep(id="1", description="生成TA/CA模板（单目录）"),
                WorkflowStep(id="2", description="补全TA/CA逻辑与接口"),
                WorkflowStep(id="3", description="optee_runner编译（build）"),
                WorkflowStep(id="4", description="optee_runner运行QEMU验证（full）"),
            ]

        return [
            WorkflowStep(id="1", description="生成TA/CA模板（单目录）"),
            WorkflowStep(id="2", description="补全TA/CA逻辑与接口"),
            WorkflowStep(id="3", description="编译验证（build）"),
        ]
