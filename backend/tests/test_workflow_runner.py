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
