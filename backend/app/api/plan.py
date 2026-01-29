"""Plan模式API - 任务规划"""
from fastapi import APIRouter, HTTPException

from app.schemas.models import (
    PlanInitRequest,
    PlanRefineRequest,
    PlanConfirmRequest,
    Workflow,
)
from app.infrastructure.logger import get_logger
from app.infrastructure.vector_store import get_vector_store
from app.core.llm import LLMFactory
from app.core.workflow import WorkflowManager

router = APIRouter()
logger = get_logger("tc_agent.api.plan")

# 内存存储workflow(生产环境应使用Redis等)
workflows: dict[str, Workflow] = {}


async def get_workflow_manager() -> WorkflowManager:
    """获取WorkflowManager实例"""
    llm = LLMFactory.create_from_config()
    try:
        vector_store = await get_vector_store()
        retriever = vector_store.get_retriever("all")
    except Exception:
        retriever = None
    return WorkflowManager(llm, retriever)


@router.post("/init")
async def init_plan(body: PlanInitRequest):
    """初始化计划,生成workflow"""
    logger.info("初始化Plan", task=body.task[:50], workspace=body.workspace_root)

    manager = await get_workflow_manager()
    workflow = await manager.generate_workflow(body.task, body.context)
    workflow.workspace_root = body.workspace_root
    workflows[workflow.id] = workflow

    logger.info("Plan生成完成", workflow_id=workflow.id, steps_count=len(workflow.steps))

    return {
        "workflow_id": workflow.id,
        "task": workflow.task,
        "steps": [s.model_dump() for s in workflow.steps],
    }


@router.post("/refine")
async def refine_plan(body: PlanRefineRequest):
    """根据用户指令修改计划"""
    if body.workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows[body.workflow_id]
    logger.info("修改Plan", workflow_id=body.workflow_id, instruction=body.instruction[:50])

    manager = await get_workflow_manager()
    workflow = await manager.refine_workflow(workflow, body.instruction)
    workflows[body.workflow_id] = workflow

    return {
        "workflow_id": workflow.id,
        "steps": [s.model_dump() for s in workflow.steps],
    }


@router.post("/confirm")
async def confirm_plan(body: PlanConfirmRequest):
    """确认计划,准备执行"""
    if body.workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows[body.workflow_id]
    workflow.status = "confirmed"
    workflows[body.workflow_id] = workflow

    logger.info("Plan已确认", workflow_id=body.workflow_id)

    return {
        "workflow_id": workflow.id,
        "status": "confirmed",
        "message": "计划已确认,可以进入Code模式执行",
    }

