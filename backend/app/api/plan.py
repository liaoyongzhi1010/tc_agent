"""Plan模式API - 任务规划"""
from fastapi import APIRouter, HTTPException
import uuid as uuid_lib

from app.schemas.models import (
    PlanInitRequest,
    PlanRefineRequest,
    PlanConfirmRequest,
    Workflow,
    WorkflowStep,
)
from app.infrastructure.logger import get_logger

router = APIRouter()
logger = get_logger("tc_agent.api.plan")

# 内存存储workflow(生产环境应使用Redis等)
workflows: dict[str, Workflow] = {}


@router.post("/init")
async def init_plan(body: PlanInitRequest):
    """初始化计划,生成workflow"""
    logger.info("初始化Plan", task=body.task[:50])

    # TODO: 集成RAG检索和LLM生成workflow
    # 目前生成占位workflow
    workflow = Workflow(
        id=str(uuid_lib.uuid4()),
        task=body.task,
        steps=[
            WorkflowStep(id="1", description="分析任务需求"),
            WorkflowStep(id="2", description="生成代码框架"),
            WorkflowStep(id="3", description="实现核心逻辑"),
            WorkflowStep(id="4", description="测试和验证"),
        ],
        status="draft",
    )
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

    # TODO: 使用LLM根据指令修改步骤
    # 目前返回原步骤
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


@router.get("/{workflow_id}")
async def get_plan(workflow_id: str):
    """获取计划详情"""
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows[workflow_id]
    return workflow.model_dump()
