# Workflow Runner Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 以“编译 TA/CA → QEMU 执行 CA → CA 退出码=0”为唯一成功标准，建立可插拔、干净的 Docker 验证闭环。

**Architecture:** 新增 `workflow_runner` 作为编译+运行的统一入口；`docker_build` 支持可选 TA 头文件挂载；`qemu_run` 支持注入 CA 并输出稳定标记；QEMU 模式由 `.env` 配置（simple/secure）。

**Tech Stack:** Python (FastAPI tools), OP-TEE build Docker image, QEMU, pytest.

---

### Task 1: 加入 QEMU 模式配置（.env + Settings + 测试）

**Files:**
- Create: `backend/tests/test_settings.py`
- Modify: `backend/app/infrastructure/config.py`
- Modify: `backend/.env.example`

**Step 1: Write the failing test**

```python
# backend/tests/test_settings.py
from app.infrastructure.config import Settings


def test_default_qemu_mode_is_simple():
    settings = Settings(_env_file=None)
    assert settings.qemu_mode == "simple"
    assert settings.qemu_test_command is None
```

**Step 2: Run test to verify it fails**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_settings.py`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'qemu_mode'`.

**Step 3: Write minimal implementation**

```python
# backend/app/infrastructure/config.py (add near other settings)
    # QEMU配置
    qemu_mode: str = "simple"  # simple, secure
    qemu_test_command: Optional[str] = None
```

**Step 4: Update .env.example**

```dotenv
# backend/.env.example (append near Agent配置)
# QEMU配置
TC_AGENT_QEMU_MODE=simple
TC_AGENT_QEMU_TEST_COMMAND=
```

**Step 5: Run test to verify it passes**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_settings.py`
Expected: PASS.

**Step 6: Commit**

```bash
git add backend/app/infrastructure/config.py backend/.env.example backend/tests/test_settings.py
git commit -m "feat: add qemu mode settings"
```

---

### Task 2: docker_build 支持 CA 编译时挂载 TA 头文件

**Files:**
- Create: `backend/tests/test_docker_build_commands.py`
- Modify: `backend/app/tools/tee/docker_build.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_docker_build_commands.py
from pathlib import Path
from app.tools.tee.docker_build import DockerBuildTool


def test_build_ca_command_mounts_ta_dir(tmp_path: Path):
    tool = DockerBuildTool()
    ca_dir = tmp_path / "demo_ca"
    ta_dir = tmp_path / "demo_ta"
    ca_dir.mkdir()
    ta_dir.mkdir()

    cmd = tool._build_ca_command(ca_dir, ca_dir, ta_dir)
    assert f"-v {ta_dir}:/workspace/{ta_dir.name} " in cmd
```

**Step 2: Run test to verify it fails**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_docker_build_commands.py`
Expected: FAIL with `AttributeError: 'DockerBuildTool' object has no attribute '_build_ca_command'`.

**Step 3: Write minimal implementation**

```python
# backend/app/tools/tee/docker_build.py
from typing import Dict, Any, Optional  # add Optional

    async def execute(..., ta_dir: str = None) -> ToolResult:
        ...
        if build_type == "ta":
            result = await self._build_ta(source_path, output_path)
        else:
            ta_path = Path(ta_dir).resolve() if ta_dir else None
            result = await self._build_ca(source_path, output_path, ta_path)

    def _build_ca_command(self, source_path: Path, output_path: Path, ta_path: Optional[Path]) -> str:
        extra_mount = ""
        if ta_path:
            if not ta_path.exists():
                raise FileNotFoundError(f"TA 目录不存在: {ta_path}")
            extra_mount = f"-v {ta_path}:/workspace/{ta_path.name} "
        return (
            f"docker run --rm "
            f"-v {source_path}:/workspace/ca "
            f"-v {output_path}:/workspace/output "
            f"{extra_mount}"
            f"-w /workspace/ca "
            f"{OPTEE_IMAGE_NAME} "
            f"bash -c 'make CROSS_COMPILE=aarch64-linux-gnu- "
            f"TEEC_EXPORT=/optee/optee_client/out/export/usr "
            f"-j$(nproc) && find . -maxdepth 1 -type f -executable -exec cp {{}} /workspace/output/ \\;'"
        )

    async def _build_ca(...):
        cmd = self._build_ca_command(source_path, output_path, ta_path)
        ...

    def get_schema(...):
        ...
        "ta_dir": {
            "type": "string",
            "description": "TA 目录路径（CA 编译时可选，含头文件）",
        },
```

**Step 4: Run test to verify it passes**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_docker_build_commands.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/tools/tee/docker_build.py backend/tests/test_docker_build_commands.py
git commit -m "feat: allow ca build to mount ta headers"
```

---

### Task 3: qemu_run 支持 CA 注入并可测试命令拼装

**Files:**
- Create: `backend/tests/test_qemu_run_commands.py`
- Modify: `backend/app/tools/tee/qemu_run.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_qemu_run_commands.py
from pathlib import Path
from app.tools.tee.qemu_run import QemuRunTool


def test_build_qemu_command_includes_ca_mount(tmp_path: Path):
    tool = QemuRunTool()
    ta_dir = tmp_path / "ta"
    ca_file = tmp_path / "demo_ca"
    ta_dir.mkdir()
    ca_file.write_text("bin")

    cmd = tool._build_qemu_command(
        ta_dir=ta_dir,
        test_script="test_ta.sh",
        test_command="/usr/bin/demo_ca",
        timeout=10,
        ca_file=ca_file,
    )
    assert f"-v {ca_file.parent}:/workspace/ca " in cmd
    assert f"/workspace/ca/{ca_file.name}" in cmd
```

**Step 2: Run test to verify it fails**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_qemu_run_commands.py`
Expected: FAIL with `AttributeError: 'QemuRunTool' object has no attribute '_build_qemu_command'`.

**Step 3: Write minimal implementation**

```python
# backend/app/tools/tee/qemu_run.py
from typing import Dict, Any, Optional

    def _build_qemu_command(
        self,
        ta_dir: Path,
        test_script: str,
        test_command: str,
        timeout: int,
        ca_file: Optional[Path],
    ) -> str:
        ca_mount = ""
        ca_arg = ""
        if ca_file:
            ca_mount = f"-v {ca_file.parent}:/workspace/ca "
            ca_arg = f"/workspace/ca/{ca_file.name}"
        return (
            f"docker run --rm "
            f"-v {ta_dir}:/workspace/ta "
            f"{ca_mount}"
            f"{OPTEE_IMAGE_NAME} "
            f"{test_script} /workspace/ta {ca_arg} '{test_command}' {timeout}"
        )

    async def execute(..., ca_file: str = None) -> ToolResult:
        ...
        ca_path = Path(ca_file).resolve() if ca_file else None
        ...
        test_script = "test_ta.sh" if secure_mode else "test_ta_simple.sh"
        cmd = self._build_qemu_command(ta_path, test_script, test_command, timeout, ca_path)
        ...

    def get_schema(...):
        ...
        "ca_file": {
            "type": "string",
            "description": "CA 可执行文件路径（可选）",
        },
```

**Step 4: Run test to verify it passes**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_qemu_run_commands.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/tools/tee/qemu_run.py backend/tests/test_qemu_run_commands.py
git commit -m "feat: qemu_run accepts ca_file"
```

---

### Task 4: Dockerfile 脚本支持 CA 注入 + 稳定标记

**Files:**
- Create: `backend/tests/test_dockerfile_markers.py`
- Modify: `backend/docker/Dockerfile.optee`

**Step 1: Write the failing test**

```python
# backend/tests/test_dockerfile_markers.py
from pathlib import Path


def test_dockerfile_has_ca_exit_code_marker():
    dockerfile = Path("backend/docker/Dockerfile.optee").read_text(encoding="utf-8")
    assert "CA_EXIT_CODE=" in dockerfile
    assert "=== TEST_COMPLETE ===" in dockerfile
    assert "Usage: test_ta.sh <ta_directory> [ca_file|test_command]" in dockerfile
    assert "Usage: test_ta_simple.sh <ta_directory> [ca_file|test_command]" in dockerfile
```

**Step 2: Run test to verify it fails**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_dockerfile_markers.py`
Expected: FAIL with missing markers.

**Step 3: Write minimal implementation**

Update `backend/docker/Dockerfile.optee`:
- `test_ta.sh` / `test_ta_simple.sh` 支持 `CA_FILE` 作为第二参数
- `rcS` 中执行 `$TEST_CMD` 后打印 `CA_EXIT_CODE=$RET`（secure）或 `CA_EXIT_CODE=SKIPPED`（simple 有 CA）
- 输出 `=== TEST_COMPLETE ===`

(具体片段按 `feat/docker-runner` 分支中 `test_ta.sh` 与 `test_ta_simple.sh` 逻辑迁移)

**Step 4: Run test to verify it passes**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_dockerfile_markers.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/docker/Dockerfile.optee backend/tests/test_dockerfile_markers.py
git commit -m "feat: qemu scripts support ca and markers"
```

---

### Task 5: 引入 workflow_runner 并更新工具注册与提示词

**Files:**
- Create: `backend/app/tools/tee/workflow_runner.py`
- Create: `backend/tests/test_workflow_runner.py`
- Modify: `backend/app/tools/registry.py`
- Modify: `backend/app/tools/tee/__init__.py`
- Modify: `backend/app/core/agent/prompts.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_workflow_runner.py
from app.tools.tee.workflow_runner import evaluate_qemu_output


def test_evaluate_qemu_output_secure_success():
    output = "=== TEST_COMPLETE ===\nCA_EXIT_CODE=0\n"
    result = evaluate_qemu_output(output, require_ca=True)
    assert result["success"] is True


def test_evaluate_qemu_output_missing_ca_fails():
    output = "=== TEST_COMPLETE ===\n"
    result = evaluate_qemu_output(output, require_ca=True)
    assert result["success"] is False
    assert "CA_EXIT_CODE" in result["reason"]


from pathlib import Path
from app.tools.tee.workflow_runner import find_executable_file


def test_find_executable_file_single(tmp_path: Path):
    exe = tmp_path / "demo"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    result = find_executable_file(tmp_path)
    assert result == exe
```

**Step 2: Run test to verify it fails**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_workflow_runner.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.tools.tee.workflow_runner'`.

**Step 3: Write minimal implementation**

```python
# backend/app/tools/tee/workflow_runner.py
from pathlib import Path
from typing import Any, Dict, Optional
import os

from app.infrastructure.config import settings
from app.infrastructure.logger import get_logger
from app.schemas.models import ToolResult
from app.tools.base import BaseTool
from app.tools.tee.docker_build import DockerBuildTool
from app.tools.tee.qemu_run import QemuRunTool

logger = get_logger("tc_agent.tools.workflow_runner")


def evaluate_qemu_output(output: str, require_ca: bool) -> Dict[str, Any]:
    has_complete = "TEST_COMPLETE" in output
    ca_marker = "CA_EXIT_CODE=" in output
    ca_ok = "CA_EXIT_CODE=0" in output
    if not has_complete:
        return {"success": False, "reason": "missing TEST_COMPLETE marker"}
    if require_ca and not ca_marker:
        return {"success": False, "reason": "missing CA_EXIT_CODE"}
    if require_ca and not ca_ok:
        return {"success": False, "reason": "CA_EXIT_CODE not zero"}
    return {"success": True, "reason": "ok"}


def find_executable_file(directory: Path) -> Path:
    candidates = [p for p in directory.iterdir() if p.is_file() and os.access(p, os.X_OK)]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError("No executable file found")
    raise ValueError("Multiple executables found")


class WorkflowRunner(BaseTool):
    name = "workflow_runner"
    description = "编译TA/CA并在QEMU中运行测试，返回结构化结果，支持secure模式CA端到端校验"

    async def execute(self, ta_dir: str, ca_dir: Optional[str] = None, timeout: int = 120) -> ToolResult:
        secure_mode = settings.qemu_mode == "secure"
        require_ca = secure_mode
        if require_ca and not ca_dir:
            return ToolResult(success=False, error="secure模式必须提供ca_dir", data={"stage": "precheck"})

        docker_build = DockerBuildTool()
        qemu_run = QemuRunTool()

        ta_build = await docker_build.execute(source_dir=ta_dir, build_type="ta")
        if not ta_build.success:
            return ToolResult(success=False, error=ta_build.error or "TA编译失败", data={"stage": "build_ta"})

        ca_exe_path: Optional[Path] = None
        if ca_dir:
            ca_build = await docker_build.execute(source_dir=ca_dir, build_type="ca", ta_dir=ta_dir)
            if not ca_build.success:
                return ToolResult(success=False, error=ca_build.error or "CA编译失败", data={"stage": "build_ca"})
            ca_exe_path = find_executable_file(Path(ca_dir))

        if settings.qemu_test_command:
            test_command = settings.qemu_test_command
        elif secure_mode and ca_exe_path:
            test_command = f"/usr/bin/{ca_exe_path.name}"
        else:
            test_command = "echo TA loaded successfully"

        ca_file = str(ca_exe_path) if ca_exe_path else None
        qemu_result = await qemu_run.execute(
            ta_dir=ta_dir,
            test_command=test_command,
            timeout=timeout,
            secure_mode=secure_mode,
            ca_file=ca_file,
        )
        if not qemu_result.success:
            return ToolResult(success=False, error=qemu_result.error or "QEMU测试失败", data={"stage": "qemu_run"})

        output = ""
        if isinstance(qemu_result.data, dict):
            output = qemu_result.data.get("output", "") or ""
        evaluation = evaluate_qemu_output(output, require_ca=require_ca)
        if not evaluation["success"]:
            return ToolResult(success=False, error=f"QEMU输出校验失败: {evaluation['reason']}", data={"stage": "qemu_run", "output": output})

        return ToolResult(success=True, data={"stage": "complete", "mode": "secure" if secure_mode else "simple", "ta_dir": ta_dir, "ca_dir": ca_dir, "output": output})

    def get_schema(self) -> Dict[str, Any]:
        return {
            "ta_dir": {"type": "string", "description": "TA 目录路径"},
            "ca_dir": {"type": "string", "description": "CA 目录路径（secure模式必填）"},
            "timeout": {"type": "integer", "description": "超时时间(秒)"},
        }
```

**Step 4: Register tool + exports + prompt**

```python
# backend/app/tools/registry.py
from app.tools.tee.workflow_runner import WorkflowRunner
...
self.register(WorkflowRunner(), "tee")
```

```python
# backend/app/tools/tee/__init__.py
from app.tools.tee.workflow_runner import WorkflowRunner

__all__ = [
    "TAGenerator",
    "CAGenerator",
    "CryptoHelper",
    "DockerBuildTool",
    "TAValidateTool",
    "QemuRunTool",
    "WorkflowRunner",
]
```

```python
# backend/app/core/agent/prompts.py (TA/CA流程段落)
4. **优先使用 workflow_runner 完成编译+运行验证**（secure模式需要CA端到端通过）
5. 如仅需编译，使用 docker_build 编译TA和CA代码（首次编译会自动构建Docker镜像，需要几分钟）
```

**Step 5: Run test to verify it passes**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_workflow_runner.py`
Expected: PASS.

**Step 6: Commit**

```bash
git add backend/app/tools/tee/workflow_runner.py backend/tests/test_workflow_runner.py backend/app/tools/registry.py backend/app/tools/tee/__init__.py backend/app/core/agent/prompts.py
git commit -m "feat: add workflow_runner end-to-end build/run"
```

---

### Task 6: AES-GCM 模板 SHORT_BUFFER 回写长度

**Files:**
- Modify: `backend/app/tools/tee/ta_generator.py`
- Modify: `backend/tests/test_aes_gcm_templates.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_aes_gcm_templates.py (append)

def test_aes_gcm_template_short_buffer_sets_size():
    gen = TAGenerator()
    result = gen._build_files(
        name="aes_demo",
        ta_uuid="12345678-1234-5678-1234-567812345678",
        template="aes_gcm_simple",
    )
    ta_c = result["aes_demo_ta.c"]
    assert "params[3].memref.size = plain_len + TAG_LEN;" in ta_c
    assert "params[3].memref.size = cipher_len;" in ta_c
```

**Step 2: Run test to verify it fails**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_aes_gcm_templates.py`
Expected: FAIL with missing strings.

**Step 3: Write minimal implementation**

```c
// backend/app/tools/tee/ta_generator.py (AES_GCM_TA_TEMPLATE)
if (out_len < plain_len + TAG_LEN) {
    EMSG("Output buffer too small");
    params[3].memref.size = plain_len + TAG_LEN;
    return TEE_ERROR_SHORT_BUFFER;
}
...
if (out_len < cipher_len) {
    EMSG("Output buffer too small");
    params[3].memref.size = cipher_len;
    return TEE_ERROR_SHORT_BUFFER;
}
```

**Step 4: Run test to verify it passes**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_aes_gcm_templates.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/tools/tee/ta_generator.py backend/tests/test_aes_gcm_templates.py
git commit -m "fix: return required size on short buffer"
```

---

### Task 7: 清理与可插拔对齐（文档与样例）

**Files:**
- Modify: `README.md`

**Step 1: Update docs to match new flow**

```markdown
# README.md (补充 .env 与生产验证说明)
- 增加 TC_AGENT_QEMU_MODE / TC_AGENT_QEMU_TEST_COMMAND 示例
- 说明生产标准 = secure 模式 CA 端到端退出码 0
```

**Step 2: Manual verification**

No automated tests. Verify README format renders and instructions remain consistent.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document qemu runner modes"
```

---

### Task 8: 全量验证（仅在实现完成后执行）

**Step 1: Run unit tests**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_settings.py backend/tests/test_docker_build_commands.py backend/tests/test_qemu_run_commands.py backend/tests/test_dockerfile_markers.py backend/tests/test_workflow_runner.py backend/tests/test_aes_gcm_templates.py`
Expected: PASS.

**Step 2: Optional smoke (Mac/simple)**

- 使用 `workflow_runner` 生成并编译 TA/CA，simple 模式运行 QEMU，确认 `TEST_COMPLETE`。

**Step 3: Optional smoke (Ubuntu/secure)**

- secure 模式运行，确认 `CA_EXIT_CODE=0`。

---

## Notes
- @superpowers:test-driven-development: 每个功能点先写测试再实现。
- @superpowers:systematic-debugging: 若出现编译或 QEMU 失败，先按该流程定位。
- @superpowers:verification-before-completion: 最终宣称成功前必须跑 Task 8。

