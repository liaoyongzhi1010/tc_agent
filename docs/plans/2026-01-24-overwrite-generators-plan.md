# Overwrite Behavior for Generators Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deterministic overwrite behavior to `ta_generator` and `ca_generator`, with prompt guidance, so repeated runs don't create new directories.

**Architecture:** Introduce an `overwrite` boolean parameter (default `true`) in both generators. If output directory exists and `overwrite=false`, return a clear error; otherwise re-generate files in-place. Update prompts to guide fixed naming and mention overwrite control.

**Tech Stack:** Python, pytest.

### Task 1: Add failing tests for overwrite behavior (@superpowers:test-driven-development)

**Files:**
- Create: `backend/tests/test_generator_overwrite.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_generator_overwrite.py -v`
Expected: FAIL (TypeError: unexpected keyword argument 'overwrite').

**Step 3: Commit**

```bash
git add backend/tests/test_generator_overwrite.py
git commit -m "test: add overwrite behavior coverage for generators"
```

### Task 2: Implement overwrite handling in TA generator (@superpowers:test-driven-development)

**Files:**
- Modify: `backend/app/tools/tee/ta_generator.py`

**Step 1: Write minimal implementation**

```python
    async def execute(
        self,
        name: str,
        output_dir: str,
        ta_uuid: str = None,
        template: str = None,
        overwrite: bool = True,
    ) -> ToolResult:
        try:
            ta_uuid = ta_uuid or str(uuid.uuid4())
            output_path = Path(output_dir) / f"{name}_ta"

            if output_path.exists() and not overwrite:
                return ToolResult(success=False, error=f"输出目录已存在: {output_path}")

            existed_before = output_path.exists()
            output_path.mkdir(parents=True, exist_ok=True)
            files = self._build_files(name=name, ta_uuid=ta_uuid, template=template)

            created_files = []
            for filename, content in files.items():
                filepath = output_path / filename
                filepath.write_text(content)
                created_files.append(str(filepath))

            logger.info("TA生成完成", name=name, uuid=ta_uuid, path=str(output_path))

            return ToolResult(
                success=True,
                data={
                    "uuid": ta_uuid,
                    "output_dir": str(output_path),
                    "files": created_files,
                    "overwritten": existed_before,
                },
            )
        except Exception as e:
            logger.error("TA生成失败", name=name, error=str(e))
            return ToolResult(success=False, error=str(e))
```

**Step 2: Update schema**

```python
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": {"type": "string", "description": "TA名称"},
            "output_dir": {"type": "string", "description": "输出目录"},
            "ta_uuid": {"type": "string", "description": "TA UUID(可选,自动生成)"},
            "template": {
                "type": "string",
                "enum": ["aes_gcm_simple"],
                "description": "可选模板：aes_gcm_simple",
            },
            "overwrite": {
                "type": "boolean",
                "description": "是否覆盖已存在目录(默认true)",
            },
        }
```

**Step 3: Run tests**

Run: `pytest backend/tests/test_generator_overwrite.py::test_ta_generator_overwrite_false_blocks -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/tools/tee/ta_generator.py
git commit -m "feat: add overwrite control to ta_generator"
```

### Task 3: Implement overwrite handling in CA generator (@superpowers:test-driven-development)

**Files:**
- Modify: `backend/app/tools/tee/ca_generator.py`

**Step 1: Write minimal implementation**

```python
    async def execute(
        self,
        name: str,
        ta_name: str,
        output_dir: str,
        template: str = None,
        overwrite: bool = True,
    ) -> ToolResult:
        try:
            output_path = Path(output_dir) / f"{name}_ca"

            if output_path.exists() and not overwrite:
                return ToolResult(success=False, error=f"输出目录已存在: {output_path}")

            existed_before = output_path.exists()
            output_path.mkdir(parents=True, exist_ok=True)
            files = self._build_files(name=name, ta_name=ta_name, template=template)

            created_files = []
            for filename, content in files.items():
                filepath = output_path / filename
                filepath.write_text(content)
                created_files.append(str(filepath))

            logger.info("CA生成完成", name=name, ta_name=ta_name, path=str(output_path))

            return ToolResult(
                success=True,
                data={
                    "output_dir": str(output_path),
                    "files": created_files,
                    "overwritten": existed_before,
                },
            )
        except Exception as e:
            logger.error("CA生成失败", name=name, error=str(e))
            return ToolResult(success=False, error=str(e))
```

**Step 2: Update schema**

```python
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": {"type": "string", "description": "CA名称"},
            "ta_name": {"type": "string", "description": "对应的TA名称"},
            "output_dir": {"type": "string", "description": "输出目录"},
            "template": {
                "type": "string",
                "enum": ["aes_gcm_simple"],
                "description": "可选模板：aes_gcm_simple",
            },
            "overwrite": {
                "type": "boolean",
                "description": "是否覆盖已存在目录(默认true)",
            },
        }
```

**Step 3: Run tests**

Run: `pytest backend/tests/test_generator_overwrite.py::test_ca_generator_overwrite_false_blocks -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/tools/tee/ca_generator.py
git commit -m "feat: add overwrite control to ca_generator"
```

### Task 4: Update prompts to enforce fixed naming and overwrite guidance

**Files:**
- Modify: `backend/app/core/agent/prompts.py`

**Step 1: Update guidance**

Add to “TA/CA开发完整流程” or “重要提示”：
- 同一任务必须使用固定 name（避免生成新目录）。
- 若需覆盖同名目录，显式传 `overwrite=true`（默认）; 如需保护现有目录，传 `overwrite=false`。

**Step 2: Run full overwrite tests**

Run: `pytest backend/tests/test_generator_overwrite.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/core/agent/prompts.py
git commit -m "docs: document overwrite usage for generators"
```

### Task 5: Final verification

**Step 1: Run focused test suite**

Run: `pytest backend/tests/test_generator_overwrite.py -v`
Expected: PASS

**Step 2: Optional full test suite**

Run: `pytest backend/tests -v`
Expected: PASS (or report failures if pre-existing)

**Step 3: Commit (if needed)**

```bash
git status -sb
```
