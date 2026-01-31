"""Workspace utilities (server-side workspace storage)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from app.infrastructure.logger import get_logger
from app.infrastructure.config import settings


WORKSPACE_ROOT = Path(settings.workspace_root).expanduser().resolve()

logger = get_logger("tc_agent.workspace")


def ensure_workspace_root() -> Path:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_ROOT


def get_workspace_path(workspace_id: str) -> Path:
    root = ensure_workspace_root()
    return (root / workspace_id).resolve()


def safe_join(workspace_path: Path, rel_path: str) -> Path:
    rel = Path(rel_path)
    if rel.is_absolute():
        raise ValueError("只允许相对路径")
    target = (workspace_path / rel).resolve()
    if workspace_path not in target.parents and target != workspace_path:
        raise ValueError("路径超出工作区范围")
    return target


def apply_file_ops(
    workspace_id: str,
    workspace_root: str,
    ops: Iterable[dict],
) -> list[str]:
    if not workspace_id:
        return []

    workspace_path = get_workspace_path(workspace_id)
    if not workspace_path.exists():
        return []

    written: list[str] = []
    for op in ops:
        path = op.get("path")
        if not path:
            continue
        rel_path = None
        if os.path.isabs(path):
            if not workspace_root:
                continue
            rel_path = os.path.relpath(path, workspace_root)
            if rel_path.startswith(".."):
                continue
        else:
            rel_path = path

        try:
            target = safe_join(workspace_path, rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = op.get("content", "")
            encoding = op.get("encoding", "utf-8")
            target.write_text(content, encoding=encoding)
            written.append(rel_path)
        except Exception as exc:
            logger.warning("apply_file_ops failed", path=path, error=str(exc))

    return written
