"""The batch hook: one suite run per batch, and blocks become context.

`post_batch.py` fires once after a batch of tool calls resolves. These tests
pin the two things it exists for: three edits in one batch run the suite once,
and a failure still reaches the model as context under this event's own name,
because a `block` here would end the turn instead of handing the failure over.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import hook_env

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"

#: A "suite" that counts how often it was started, in the repo it ran in.
COUNTER = (
    "import pathlib; p = pathlib.Path('runs.txt'); "
    "n = int(p.read_text()) if p.exists() else 0; p.write_text(str(n + 1))"
)
FAILING = COUNTER + "; raise SystemExit('FAILED tests/test_x.py::test_y - boom')"

ENGINE = """
[project]
name = "Batchy"
source_root = "src"

[tests]
dir = "tests"
command = ["-c", {command!r}]
root_marker = "pyproject.toml"

[dependencies]
enabled = false

[artifact]
enabled = false

[scan]
enabled = false
"""


def module():
    spec = importlib.util.spec_from_file_location("post_batch", HOOKS / "post_batch.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HOOKS))
    try:
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(HOOKS))
    return mod


def project(tmp_path: Path, command: str) -> Path:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "engine.toml").write_text(ENGINE.format(command=command), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='b'\nversion='0'\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    for name in ("src/a.py", "src/b.py", "tests/test_x.py"):
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# notes\n", encoding="utf-8")
    return tmp_path


def batch(root: Path, *names: str) -> dict:
    return {
        "hook_event_name": "PostToolBatch", "session_id": "b1",
        "tool_calls": [
            {"tool_name": "Edit", "tool_input": {"file_path": str(root / n)},
             "tool_use_id": f"t{i}", "tool_response": "serialized text"}
            for i, n in enumerate(names)
        ] + [{"tool_name": "Read", "tool_input": {"file_path": str(root / "src" / "a.py")}}],
    }


def fire(root: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / "post_batch.py")],
        input=json.dumps(payload), capture_output=True, text=True, timeout=120,
        env=hook_env(root),
    )


def test_edited_paths_keeps_editor_writes_only_and_dedupes() -> None:
    mod = module()
    payload = {"tool_calls": [
        {"tool_name": "Edit", "tool_input": {"file_path": "C:\\r\\src\\a.py"}},
        {"tool_name": "Write", "tool_input": {"file_path": "C:/r/src/a.py"}},
        {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "C:/r/nb.ipynb"}},
        {"tool_name": "Read", "tool_input": {"file_path": "C:/r/src/b.py"}},
        {"tool_name": "Bash", "tool_input": {"command": "echo"}},
        "not a dict",
    ]}
    assert mod.edited_paths(payload) == ["C:/r/src/a.py", "C:/r/nb.ipynb"]


def test_merge_turns_a_block_into_context_under_this_event() -> None:
    mod = module()
    out = mod.merge([
        None,
        {"decision": "block", "reason": "Tests FAILED", "systemMessage": "red"},
        {"systemMessage": "audit ok"},
        {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "cves"}},
    ])
    assert "decision" not in out
    assert out["systemMessage"] == "red audit ok"
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolBatch"
    assert out["hookSpecificOutput"]["additionalContext"] == "Tests FAILED\n\ncves"
    assert mod.merge([None, {}]) is None


def test_three_edits_in_one_batch_run_the_suite_once(tmp_path: Path) -> None:
    root = project(tmp_path, COUNTER)
    result = fire(root, batch(root, "src/a.py", "src/b.py", "tests/test_x.py", "notes.md"))
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip(), "a green suite must stay silent"
    assert (root / "runs.txt").read_text() == "1"


def test_a_failing_suite_reaches_the_session_as_context(tmp_path: Path) -> None:
    root = project(tmp_path, FAILING)
    result = fire(root, batch(root, "src/a.py", "src/b.py"))
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "decision" not in out, "a block on this event would end the turn"
    extra = out["hookSpecificOutput"]
    assert extra["hookEventName"] == "PostToolBatch"
    assert "Tests FAILED after editing" in extra["additionalContext"]
    assert "src/a.py" in extra["additionalContext"]
    assert (root / "runs.txt").read_text() == "1"


def test_a_batch_without_edits_is_silent(tmp_path: Path) -> None:
    root = project(tmp_path, COUNTER)
    result = fire(root, {"hook_event_name": "PostToolBatch", "tool_calls": [
        {"tool_name": "Read", "tool_input": {"file_path": str(root / "src" / "a.py")}},
    ]})
    assert result.returncode == 0 and not result.stdout.strip()
    assert not (root / "runs.txt").exists()


@pytest.mark.parametrize("bad", ["", "not json", "[1, 2]", '{"tool_calls": "nope"}'])
def test_a_malformed_batch_payload_is_survived(tmp_path: Path, bad: str) -> None:
    root = project(tmp_path, COUNTER)
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / "post_batch.py")],
        input=bad, capture_output=True, text=True, timeout=60,
        env=hook_env(root),
    )
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip()
