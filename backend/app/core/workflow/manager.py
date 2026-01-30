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
            steps = self._parse_workflow_response(response)
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
            new_steps = self._parse_workflow_response(response)
            workflow.steps = new_steps
        except Exception as e:
            logger.error("修改workflow失败", error=str(e))
            # 保持原样

        return workflow

    def _parse_workflow_response(self, response: str) -> List[WorkflowStep]:
        """解析LLM返回的workflow"""
        try:
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
                step = WorkflowStep(
                    id=str(item.get("id", len(steps) + 1)),
                    description=item.get("description", ""),
                    status="pending",
                )
                steps.append(step)

            if not steps:
                raise ValueError("No steps parsed")

            return steps

        except Exception as e:
            logger.warning("解析workflow失败，使用默认", error=str(e))
            return self._get_default_steps("")

    def _get_default_steps(self, task: str) -> List[WorkflowStep]:
        """返回默认工作流步骤"""
        default_steps = [
            WorkflowStep(id="1", description="创建TA/CA项目结构（仅一次）"),
            WorkflowStep(id="2", description="实现核心加密逻辑并完善接口"),
            WorkflowStep(id="3", description="编译并进行基础验证"),
        ]
        return default_steps
