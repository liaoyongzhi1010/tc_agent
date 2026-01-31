"""Workspace sync API."""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, HTTPException

from app.infrastructure.logger import get_logger
from app.infrastructure.workspace import get_workspace_path, safe_join, ensure_workspace_root
from app.schemas.models import WorkspaceInitResponse, WorkspaceSyncRequest

router = APIRouter()
logger = get_logger("tc_agent.api.workspace")


@router.post("/init", response_model=WorkspaceInitResponse)
async def init_workspace() -> WorkspaceInitResponse:
    """创建新的后端工作区"""
    ensure_workspace_root()
    workspace_id = str(uuid.uuid4())
    path = get_workspace_path(workspace_id)
    path.mkdir(parents=True, exist_ok=True)
    logger.info("Workspace created", workspace_id=workspace_id, path=str(path))
    return WorkspaceInitResponse(workspace_id=workspace_id)


@router.post("/sync")
async def sync_workspace(payload: WorkspaceSyncRequest):
    """同步文件到后端工作区"""
    workspace_path = get_workspace_path(payload.workspace_id)
    if not workspace_path.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    written: List[str] = []
    for f in payload.files:
        try:
            target = safe_join(workspace_path, f.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f.content or "", encoding=f.encoding or "utf-8")
            written.append(f.path)
        except Exception as exc:
            logger.warning("Workspace sync failed", path=f.path, error=str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"written": written, "count": len(written)}

