"""The interpreter shim: one Python startup per hook, and the fallthrough.

`run.sh` used to prove an interpreter's version with one process and run the
hook with a second. Now `_boot.py` runs inside the candidate interpreter,
checks its own version, and runs the hook in-process, exiting 3 when it is too
old so `run.sh` can try the next candidate. These tests pin the three things
that would fail quietly if they drifted: the bootstrap parses on an old
interpreter, a too-old interpreter yields exit 3 without touching stdin, and
`run.sh` forwards the hook's own exit code through the shim.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import hook_env

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
BOOT = HOOKS / "_boot.py"

ROUTING = """
[settings]
fresh_hours = 24

[[rule]]
id = "data-model"
paths = ["src/models.py"]
agents = ["systems-architect"]
level = "required"
question = "State the field."
why = "A shipped column is a migration."
"""


def _boot_module():
    spec = importlib.util.spec_from_file_location("_boot", BOOT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def routed(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    (claude / "agents").mkdir(parents=True)
    (claude / "engine.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (claude / "routing.toml").write_text(ROUTING, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "models.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def payload_for(project: Path) -> str:
    return json.dumps({
        "tool_name": "Edit", "session_id": "boot-1",
        "tool_input": {"file_path": str(project / "src" / "models.py")},
    })


def test_the_bootstrap_parses_without_modern_syntax() -> None:
    """It must reach its version check on any interpreter, however old."""
    tree = ast.parse(BOOT.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        assert not isinstance(node, ast.JoinedStr), "an f-string fails to parse on 3.5"
        assert not isinstance(node, ast.AnnAssign), "a variable annotation fails on 3.5"
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None, "a return annotation fails on 2.x"
        if isinstance(node, ast.ImportFrom):
            assert node.module != "__future__", "a __future__ import fails on 2.x"


def test_a_too_old_interpreter_exits_3(monkeypatch) -> None:
    boot = _boot_module()
    monkeypatch.setattr(sys, "version_info", (3, 10, 0, "final", 0))
    monkeypatch.setattr(sys, "argv", ["_boot.py", str(HOOKS / "consult_router.py")])
    assert boot.main() == 3


def test_the_bootstrap_runs_the_hook_in_process(routed: Path) -> None:
    """Exit 2 from the router comes straight out of the bootstrap process."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(BOOT), str(HOOKS / "consult_router.py")],
        input=payload_for(routed), capture_output=True, text=True, timeout=60,
        env=hook_env(routed),
    )
    assert result.returncode == 2, result.stderr
    assert "CONSULT OWED" in result.stderr


def test_the_bootstrap_is_silent_in_an_unconfigured_repository(tmp_path: Path) -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(BOOT), str(HOOKS / "consult_router.py")],
        input=payload_for(tmp_path), capture_output=True, text=True, timeout=60,
        env=hook_env(tmp_path),
    )
    assert result.returncode == 0
    assert not result.stdout.strip() and not result.stderr.strip()


def _shim(directory: Path, name: str, body: str) -> None:
    """A shell-script stand-in for an interpreter, found by `command -v`."""
    path = directory / name
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_run_sh_falls_through_a_too_old_candidate_and_keeps_stdin(
    routed: Path, tmp_path: Path,
) -> None:
    """A first candidate that exits 3 must not cost the real one its payload.

    `python3` is a shim that exits 3 the way `_boot.py` does on an old
    interpreter; `python` is a shim that hands off to the real interpreter.
    With the candidate order forced to python3-first, `run.sh` must move on
    and the router must still see the edit.
    """
    shims = tmp_path / "shims"
    shims.mkdir()
    _shim(shims, "python3", "exit 3")
    real = Path(sys.executable).as_posix()
    _shim(shims, "python", f'exec "{real}" "$@"')

    sh = shutil.which("sh")
    assert sh is not None
    # Native PATH format on purpose: a POSIX sh on Windows converts it.
    env = hook_env(routed, PATH=os.pathsep.join([str(shims), str(Path(sh).parent)]), OS="")
    result = subprocess.run(  # noqa: S603
        [sh, str(HOOKS / "run.sh"), "consult_router"],
        input=payload_for(routed), capture_output=True, text=True, timeout=120, env=env,
    )
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "CONSULT OWED" in result.stderr


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_run_sh_warns_once_when_every_candidate_is_too_old(
    routed: Path, tmp_path: Path,
) -> None:
    shims = tmp_path / "shims"
    shims.mkdir()
    _shim(shims, "python3", "exit 3")
    _shim(shims, "python", "exit 3")
    sh = shutil.which("sh")
    assert sh is not None
    data = tmp_path / "data"
    env = hook_env(routed, PATH=os.pathsep.join([str(shims), str(Path(sh).parent)]), OS="",
                   CLAUDE_PLUGIN_DATA=str(data))
    first = subprocess.run(  # noqa: S603
        [sh, str(HOOKS / "run.sh"), "consult_router"],
        input=payload_for(routed), capture_output=True, text=True, timeout=120, env=env,
    )
    assert first.returncode == 0
    assert "needs Python 3.11" in first.stdout
    second = subprocess.run(  # noqa: S603
        [sh, str(HOOKS / "run.sh"), "consult_router"],
        input=payload_for(routed), capture_output=True, text=True, timeout=120, env=env,
    )
    assert second.returncode == 0
    assert not second.stdout.strip(), "the warning must not repeat within a session"
