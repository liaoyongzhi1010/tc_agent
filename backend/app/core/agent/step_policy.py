"""Agent step policy and classification."""
from __future__ import annotations

from enum import Enum
from typing import List
import re


class StepKind(str, Enum):
    GENERATE = "generate"
    IMPLEMENT = "implement"
    BUILD = "build"
    RUN = "run"
    GENERIC = "generic"


class StepPolicy:
    """Classify steps and provide tool allowance."""

    def classify(self, description: str) -> StepKind:
        text = (description or "").strip()
        upper = text.upper()

        def has_token(token: str) -> bool:
            pattern = rf"(?:^|[^A-Z0-9]){re.escape(token)}(?:[^A-Z0-9]|$)"
            return re.search(pattern, upper) is not None

        has_ta_ca = any(
            has_token(token) for token in ("TA", "CA", "OP-TEE", "OPTEE", "TEE")
        ) or ("可信应用" in text)

        if has_ta_ca and any(k in text for k in ("生成", "模板")):
            return StepKind.GENERATE
        if any(k in text for k in ("实现", "逻辑", "修改", "补全", "完善")):
            return StepKind.IMPLEMENT
        if "编译" in text or "build" in text:
            return StepKind.BUILD
        if any(k in text for k in ("运行", "QEMU", "测试", "验证")):
            return StepKind.RUN
        return StepKind.GENERIC

    def allowed_tools(self, kind: StepKind) -> List[str]:
        if kind in (StepKind.IMPLEMENT, StepKind.GENERIC):
            return ["file_read", "file_write", "crypto_helper"]
        return []

    def runner_mode(self, kind: StepKind, build_done: bool) -> str | None:
        if kind == StepKind.BUILD:
            return "build"
        if kind == StepKind.RUN:
            return "test" if build_done else "full"
        return None
