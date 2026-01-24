from app.infrastructure.config import Settings


def test_default_qemu_mode_is_simple():
    settings = Settings(_env_file=None)
    assert settings.qemu_mode == "simple"
    assert settings.qemu_test_command is None
