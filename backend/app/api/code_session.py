"""WebSocket code execution session."""
from __future__ import annotations

import asyncio
import uuid
from typing import Awaitable, Callable

from fastapi import WebSocket, WebSocketDisconnect

from app.core.agent import ReActAgent
from app.infrastructure.logger import get_logger
from app.schemas.models import ToolResult
from app.infrastructure.workflow_store import WorkflowStore

logger = get_logger("tc_agent.api.code_session")


class CodeSession:
    def __init__(
        self,
        websocket: WebSocket,
        workflow_id: str,
        workflow_store: WorkflowStore,
        agent_factory: Callable[[], ReActAgent],
    ) -> None:
        self.websocket = websocket
        self.workflow_id = workflow_id
        self.workflow_store = workflow_store
        self.agent_factory = agent_factory
        self.cancel_event = asyncio.Event()
        self.pending_requests: dict[str, asyncio.Future] = {}
        self.receiver_task: asyncio.Task | None = None

    async def run(self) -> None:
        await self.websocket.accept()
        logger.info("Agent执行WebSocket连接", workflow_id=self.workflow_id)

        try:
            workflow = await self.workflow_store.get(self.workflow_id)
            if not workflow:
                await self._send_error("Workflow not found")
                return
            if workflow.status != "confirmed":
                await self._send_error("Workflow not confirmed")
                return

            self.receiver_task = asyncio.create_task(self._receive())

            agent = self.agent_factory()
            async for event in agent.run(
                workflow.task,
                workflow,
                workflow.workspace_root,
                self._request_file,
                self.cancel_event,
            ):
                logger.info("发送事件", event_type=event.type)
                await self.websocket.send_json({"type": event.type, "data": event.data})
                if event.type == "cancelled":
                    break

        except WebSocketDisconnect:
            logger.info("WebSocket断开连接", workflow_id=self.workflow_id)
        except Exception as exc:
            logger.error("执行出错", error=str(exc))
            try:
                await self._send_error(str(exc))
            except Exception:
                pass
        finally:
            if self.receiver_task:
                self.receiver_task.cancel()
            try:
                await self.websocket.close()
            except Exception:
                pass

    async def _receive(self) -> None:
        while True:
            try:
                message = await self.websocket.receive_json()
            except WebSocketDisconnect:
                self.cancel_event.set()
                break
            except Exception:
                self.cancel_event.set()
                break
            msg_type = message.get("type")
            if msg_type == "cancel":
                self.cancel_event.set()
                break
            if msg_type == "file_read_response":
                data = message.get("data") or {}
                request_id = data.get("request_id")
                fut = self.pending_requests.pop(request_id, None)
                if fut and not fut.done():
                    fut.set_result(data)

    async def _request_file(self, path: str, encoding: str = "utf-8") -> ToolResult:
        request_id = str(uuid.uuid4())
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = fut
        await self.websocket.send_json(
            {
                "type": "file_read_request",
                "data": {
                    "request_id": request_id,
                    "path": path,
                    "encoding": encoding,
                },
            }
        )
        try:
            data = await asyncio.wait_for(fut, timeout=30)
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            return ToolResult(success=False, error="前端读取文件超时")

        if data.get("ok"):
            content = data.get("content", "")
            return ToolResult(
                success=True,
                data={"path": path, "content": content, "size": len(content)},
            )
        return ToolResult(success=False, error=data.get("error", "前端读取失败"))

    async def _send_error(self, message: str) -> None:
        await self.websocket.send_json({"type": "error", "message": message})
