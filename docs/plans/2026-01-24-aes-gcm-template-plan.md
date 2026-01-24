# AES-GCM Template Generator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic AES-GCM “simple” TA/CA template generator so the assistant always produces correct, compilable code with fixed command IDs and parameter layout.

**Architecture:** Extend `ta_generator` and `ca_generator` with an optional `template` parameter. For `template="aes_gcm_simple"`, emit fixed TA/CA code: two commands (encrypt/decrypt) using 4 memref params, output `cipher||tag` for encrypt and `plain` for decrypt. Add a small test suite to validate template selection and key strings in output.

**Tech Stack:** Python tools (generator classes), Pydantic tests with pytest, OP-TEE TA/CA C templates.

---

## Task 0: Ensure test tooling is available

**Files:** none

**Step 1: Verify pytest available (tc_agent env)**

Run: `conda run -n tc_agent python -m pytest -q --version`
Expected: prints pytest version

---

## Task 1: Add AES-GCM template option to TA generator

**Files:**
- Modify: `backend/app/tools/tee/ta_generator.py`
- Test: `backend/tests/test_aes_gcm_templates.py`

**Step 1: Write the failing test**

Create `backend/tests/test_aes_gcm_templates.py`:

```python
from app.tools.tee.ta_generator import TAGenerator


def test_ta_generator_aes_gcm_template_includes_commands(tmp_path):
    gen = TAGenerator()
    result = gen._build_files(name="aes_demo", ta_uuid="12345678-1234-5678-1234-567812345678", template="aes_gcm_simple")
    ta_c = result["aes_demo_ta.c"]
    ta_h = result["aes_demo_ta.h"]
    assert "TA_CMD_AES_GCM_ENCRYPT" in ta_h
    assert "TA_CMD_AES_GCM_DECRYPT" in ta_h
    assert "do_aes_gcm_encrypt" in ta_c
    assert "do_aes_gcm_decrypt" in ta_c
```

**Step 2: Run test to verify it fails**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_aes_gcm_templates.py`
Expected: FAIL because `_build_files` or template support doesn’t exist

**Step 3: Implement minimal template support**

In `ta_generator.py`:
- Add `_build_files(...)` helper to return dict of filename→content.
- Add `template` optional param in `execute()` and `get_schema()`.
- Add `AES_GCM_TA_TEMPLATE` and `AES_GCM_HEADER_TEMPLATE` with fixed command IDs and params.

**Step 4: Run test to verify it passes**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_aes_gcm_templates.py`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/tools/tee/ta_generator.py backend/tests/test_aes_gcm_templates.py
git commit -m "feat: add aes gcm template to ta generator"
```

---

## Task 2: Add AES-GCM template option to CA generator

**Files:**
- Modify: `backend/app/tools/tee/ca_generator.py`
- Test: `backend/tests/test_aes_gcm_templates.py`

**Step 1: Write the failing test**

Extend `backend/tests/test_aes_gcm_templates.py`:

```python
from app.tools.tee.ca_generator import CAGenerator


def test_ca_generator_aes_gcm_template_includes_commands(tmp_path):
    gen = CAGenerator()
    result = gen._build_files(name="aes_demo", ta_name="aes_demo", template="aes_gcm_simple")
    ca_c = result["aes_demo.c"]
    assert "TA_CMD_AES_GCM_ENCRYPT" in ca_c
    assert "TA_CMD_AES_GCM_DECRYPT" in ca_c
```

**Step 2: Run test to verify it fails**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_aes_gcm_templates.py`
Expected: FAIL because `_build_files` or template support doesn’t exist

**Step 3: Implement template support**

In `ca_generator.py`:
- Add `_build_files(...)` helper.
- Add `template` param in `execute()` and `get_schema()`.
- Add `AES_GCM_CA_TEMPLATE` with:
  - Two commands (encrypt/decrypt)
  - Param layout: key, iv, input, output
  - Output for encrypt: cipher||tag (tag length 16)
  - Output for decrypt: plaintext

**Step 4: Run test to verify it passes**

Run: `conda run -n tc_agent python -m pytest -q backend/tests/test_aes_gcm_templates.py`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/tools/tee/ca_generator.py backend/tests/test_aes_gcm_templates.py
git commit -m "feat: add aes gcm template to ca generator"
```

---

## Task 3: Update agent guidance to prefer template option

**Files:**
- Modify: `backend/app/core/agent/prompts.py`

**Step 1: Update prompt guidance**

Add guidance: when user asks for AES-GCM TA/CA, use `template="aes_gcm_simple"` with `ta_generator`/`ca_generator` to avoid mismatched params.

**Step 2: Commit**

```bash
git add backend/app/core/agent/prompts.py
git commit -m "docs: guide agent to use aes gcm template"
```

---

## Task 4: Optional smoke check (manual)

**Files:** none

**Step 1: Generate AES-GCM TA/CA**
- Use tools with `template="aes_gcm_simple"`.

**Step 2: Build with docker_build**
- `docker_build` for TA and CA.

**Step 3: Run simple mode test**
- `workflow_runner` with `TC_AGENT_QEMU_MODE=simple`.

