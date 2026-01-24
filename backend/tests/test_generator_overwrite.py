import asyncio
from pathlib import Path

from app.tools.tee.ta_generator import TAGenerator
from app.tools.tee.ca_generator import CAGenerator

UUID = "12345678-1234-5678-1234-567812345678"


def test_ta_generator_overwrite_false_blocks(tmp_path: Path):
    gen = TAGenerator()
    res1 = asyncio.run(gen.execute(name="demo", output_dir=str(tmp_path), ta_uuid=UUID))
    assert res1.success is True

    res2 = asyncio.run(
        gen.execute(
            name="demo",
            output_dir=str(tmp_path),
            ta_uuid=UUID,
            overwrite=False,
        )
    )
    assert res2.success is False
    assert "已存在" in (res2.error or "")


def test_ta_generator_overwrite_true_rewrites(tmp_path: Path):
    gen = TAGenerator()
    res1 = asyncio.run(gen.execute(name="demo", output_dir=str(tmp_path), ta_uuid=UUID))
    assert res1.success is True

    out_dir = Path(res1.data["output_dir"])
    ta_c = out_dir / "demo_ta.c"
    ta_c.write_text("changed")

    res2 = asyncio.run(
        gen.execute(
            name="demo",
            output_dir=str(tmp_path),
            ta_uuid=UUID,
            overwrite=True,
        )
    )
    assert res2.success is True
    assert "Trusted Application" in ta_c.read_text()


def test_ca_generator_overwrite_false_blocks(tmp_path: Path):
    gen = CAGenerator()
    res1 = asyncio.run(gen.execute(name="demo", ta_name="demo", output_dir=str(tmp_path)))
    assert res1.success is True

    res2 = asyncio.run(
        gen.execute(
            name="demo",
            ta_name="demo",
            output_dir=str(tmp_path),
            overwrite=False,
        )
    )
    assert res2.success is False
    assert "已存在" in (res2.error or "")


def test_ca_generator_overwrite_true_rewrites(tmp_path: Path):
    gen = CAGenerator()
    res1 = asyncio.run(gen.execute(name="demo", ta_name="demo", output_dir=str(tmp_path)))
    assert res1.success is True

    out_dir = Path(res1.data["output_dir"])
    ca_c = out_dir / "demo.c"
    ca_c.write_text("changed")

    res2 = asyncio.run(
        gen.execute(
            name="demo",
            ta_name="demo",
            output_dir=str(tmp_path),
            overwrite=True,
        )
    )
    assert res2.success is True
    assert "Client Application" in ca_c.read_text()
