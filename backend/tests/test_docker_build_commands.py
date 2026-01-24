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
