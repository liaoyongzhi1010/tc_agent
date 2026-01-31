"""Docker Runner 集成测试（可选，依赖本地 Docker 与镜像）。"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import app.infrastructure.workspace as workspace_module
from app.tools.tee.optee_runner import _run_inline
from app.tools.tee.ta_generator import TAGenerator
from app.tools.tee.ca_generator import CAGenerator


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def _image_ok(image: str) -> bool:
    res = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return res.returncode == 0


def _docker_mount_ok(image: str, path: Path) -> bool:
    res = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{path}:/workspace",
            image,
            "bash",
            "-lc",
            "true",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return res.returncode == 0


def _select_workspace_root(image: str, tmp_path: Path) -> Path | None:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [tmp_path, repo_root / "workspace" / ".tc_agent_test"]
    for base in candidates:
        base.mkdir(parents=True, exist_ok=True)
        if _docker_mount_ok(image, base):
            return base
    return None


@pytest.mark.asyncio
async def test_optee_runner_build_docker(tmp_path, monkeypatch):
    # 需要本地 Docker 与 OP-TEE 镜像
    image = os.getenv("TC_AGENT_OPTEE_IMAGE", "tc-agent/optee-build:4.0")
    if not _docker_ok() or not _image_ok(image):
        pytest.skip("Docker 或镜像不可用，跳过集成测试")

    workspace_id = "ws-it"
    base_root = _select_workspace_root(image, tmp_path)
    if not base_root:
        pytest.skip("Docker 不允许挂载路径，跳过集成测试")

    # 设置后端工作区根目录（必须与生成位置一致）
    monkeypatch.setattr(workspace_module, "WORKSPACE_ROOT", base_root)

    workspace_root = base_root / workspace_id
    workspace_root.mkdir(parents=True, exist_ok=True)

    # 生成 TA/CA 工程
    ta_gen = TAGenerator()
    ca_gen = CAGenerator()

    ta_res = await ta_gen.execute(name="demo", output_dir=str(workspace_root))
    assert ta_res.success

    ca_res = await ca_gen.execute(name="demo", ta_name="demo", output_dir=str(workspace_root))
    assert ca_res.success

    # 只做 build 验证
    result = await _run_inline(
        workspace_id=workspace_id,
        ta_dir="demo_ta",
        ca_dir="demo_ca",
        mode="build",
        timeout=600,
    )
    assert result.success


@pytest.mark.asyncio
async def test_optee_runner_qemu_full(tmp_path, monkeypatch):
    # 需要显式开启该测试（避免默认跑 QEMU）
    if os.getenv("TC_AGENT_IT_RUN_QEMU") != "1":
        pytest.skip("未开启 QEMU 集成测试")

    image = os.getenv("TC_AGENT_OPTEE_IMAGE", "tc-agent/optee-build:4.0")
    if not _docker_ok() or not _image_ok(image):
        pytest.skip("Docker 或镜像不可用，跳过集成测试")

    workspace_id = "ws-it-qemu"
    base_root = _select_workspace_root(image, tmp_path)
    if not base_root:
        pytest.skip("Docker 不允许挂载路径，跳过集成测试")

    monkeypatch.setattr(workspace_module, "WORKSPACE_ROOT", base_root)

    workspace_root = base_root / workspace_id
    workspace_root.mkdir(parents=True, exist_ok=True)

    ta_gen = TAGenerator()
    ca_gen = CAGenerator()

    ta_res = await ta_gen.execute(name="demo", output_dir=str(workspace_root))
    assert ta_res.success

    ca_res = await ca_gen.execute(name="demo", ta_name="demo", output_dir=str(workspace_root))
    assert ca_res.success

    # build + test（包含 QEMU）
    result = await _run_inline(
        workspace_id=workspace_id,
        ta_dir="demo_ta",
        ca_dir="demo_ca",
        mode="full",
        timeout=1200,
    )
    assert result.success
