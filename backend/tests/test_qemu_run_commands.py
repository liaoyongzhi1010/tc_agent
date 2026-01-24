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
