"""TC Agent 数据模型"""
from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class Mode(str, Enum):
    """工作模式"""
    ASK = "ask"
    PLAN = "plan"
    CODE = "code"


class WorkflowStep(BaseModel):
    """工作流步骤"""
    id: str
    description: str
    status: str = "pending"  # pending | in_progress | completed | failed
    sub_steps: Optional[List["WorkflowStep"]] = None


class Workflow(BaseModel):
    """工作流"""
    id: str
    task: str
    steps: List[WorkflowStep]
    status: str = "draft"  # draft | confirmed | running | completed | failed
    current_step: int = 0
    workspace_root: Optional[str] = None


class RetrievedDoc(BaseModel):
    """检索到的文档"""
    content: str
    metadata: dict
    score: float


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None


class AgentEvent(BaseModel):
    """Agent事件"""
    type: str  # thought, action, observation, file_edit, error, complete
    data: dict


class LLMConfig(BaseModel):
    """LLM配置"""
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096


# Ask模式
class AskRequest(BaseModel):
    """Ask请求"""
    query: str
    knowledge_type: Optional[str] = "all"  # all, text, code
    model: Optional[str] = None


class AskResponse(BaseModel):
    """Ask响应"""
    answer: str
    sources: List[dict]


# Plan模式
class PlanInitRequest(BaseModel):
    """Plan初始化请求"""
    task: str
    context: Optional[str] = None
    workspace_root: Optional[str] = None


class PlanRefineRequest(BaseModel):
    """Plan修改请求"""
    workflow_id: str
    instruction: str


class PlanConfirmRequest(BaseModel):
    """Plan确认请求"""
    workflow_id: str


# Code模式
class CodeExecuteRequest(BaseModel):
    """Code执行请求"""
    task: str
    workflow_id: Optional[str] = None
    workspace_root: Optional[str] = None


# 知识库
class AddDocumentRequest(BaseModel):
    """添加文档请求"""
    content: str
    metadata: dict = Field(default_factory=dict)
    collection: str = "text"


class AddDirectoryRequest(BaseModel):
    """添加目录请求"""
    path: str
    collection: str = "code"
    file_patterns: List[str] = Field(default_factory=lambda: ["*.c", "*.h", "*.py"])
