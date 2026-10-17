"""The one failure the test hook reports instead of blocking.

`test_permanent_refusals.py` ships red on purpose. Left as a block, that one
deliberate failure stopped every source edit after init until someone filled
the list. These tests pin the detector to exactly that shape: one failed test,
the refusals test, nothing else. Anything else still blocks.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import hook_env

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
TEMPLATE_TEST = ROOT / "templates" / "tests" / "test_permanent_refusals.py"

ONLY_REFUSALS = """\
F..                                                                      [100%]
=================================== FAILURES ===================================
____________ test_the_refusal_list_has_been_filled_in ____________
AssertionError: REFUSALS is empty. Either fill it ...
=========================== short test summary info ============================
FAILED tests/test_permanent_refusals.py::test_the_refusal_list_has_been_filled_in - AssertionError: REFUSALS is empty.
1 failed, 2 passed in 0.05s
"""


def module():
    spec = importlib.util.spec_from_file_location("backend_tests", HOOKS / "backend_tests.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HOOKS))
    try:
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(HOOKS))
    return mod


def test_the_detector_accepts_exactly_the_unfilled_refusals_shape() -> None:
    assert module().only_unfilled_refusals(ONLY_REFUSALS)


def test_the_detector_rejects_anything_else() -> None:
    mod = module()
    two = ONLY_REFUSALS.replace(
        "1 failed, 2 passed",
        "2 failed, 1 passed").replace(
        "short test summary info ====\n",
        "short test summary info ====\nFAILED tests/test_models.py::test_x - boom\n")
    assert not mod.only_unfilled_refusals(two)
    other = ONLY_REFUSALS.replace("test_the_refusal_list_has_been_filled_in", "test_something_else")
    assert not mod.only_unfilled_refusals(other)
    error = ONLY_REFUSALS + "ERROR tests/test_models.py - ImportError\n"
    assert not mod.only_unfilled_refusals(error)
    assert not mod.only_unfilled_refusals("")


def test_an_unfilled_refusals_list_is_reported_not_blocked(tmp_path: Path) -> None:
    """The real template test, the real runner, through the real hook."""
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "engine.toml").write_text(
        '[project]\nname = "Acme"\nsource_root = "src"\n\n[tests]\ndir = "tests"\n'
        'root_marker = "pyproject.toml"\n\n[scan]\nenabled = false\n', encoding="utf-8")
    (claude / "vision.md").write_text("# vision\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# Acme\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='acme'\nversion='0'\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    tests = tmp_path / "tests"
    tests.mkdir()
    shutil.copy(TEMPLATE_TEST, tests / "test_permanent_refusals.py")
    edited = tests / "test_permanent_refusals.py"

    env = hook_env(tmp_path)
    payload = json.dumps({"tool_input": {"file_path": str(edited)}, "session_id": "r1"})
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / "backend_tests.py")],
        input=payload, capture_output=True, text=True, timeout=180, env=env,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "decision" not in out, out
    assert "refusals" in out["systemMessage"].lower()
    assert "test_the_refusal_list_has_been_filled_in" in out["hookSpecificOutput"]["additionalContext"]

    # A second, real failure beside it blocks as it always did.
    (tests / "test_models.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / "backend_tests.py")],
        input=payload, capture_output=True, text=True, timeout=180, env=env,
    )
    out = json.loads(result.stdout)
    assert out["decision"] == "block"
    assert "test_models.py" in out["reason"]
