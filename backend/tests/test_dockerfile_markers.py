from pathlib import Path


def test_dockerfile_has_ca_exit_code_marker():
    dockerfile_path = Path(__file__).resolve().parents[1] / "docker" / "Dockerfile.optee"
    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    assert "CA_EXIT_CODE=" in dockerfile
    assert "=== TEST_COMPLETE ===" in dockerfile
    assert "Usage: test_ta.sh <ta_directory> [ca_file|test_command]" in dockerfile
    assert "Usage: test_ta_simple.sh <ta_directory> [ca_file|test_command]" in dockerfile
