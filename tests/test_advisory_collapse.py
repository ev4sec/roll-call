"""Repeat-prone advisories collapse after their first emission, never silence.

Two guard hooks emit the same additionalContext on every relevant edit while a
condition persists: backend_tests while a suite hangs, dependency_audit while
pip-audit is missing. The full advisory teaches; the copies only spend
context. The collapse rule and its one non-negotiable: the repeat emission is
one line that still says the condition holds, because both hooks are silent on
success and a fully suppressed warning would make "still broken" look exactly
like "clean".

Every fallback is tested in the fail-open direction: no plugin data dir or no
session id means the full advisory on every occurrence, which is the pre-0.2
behavior.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"

sys.path.insert(0, str(HOOKS))
import _engine  # noqa: E402


def run_hook(hook: str, payload: dict, project: Path,
             plugin_data: Path | None = None, with_path: bool = False):
    env = {"CLAUDE_PROJECT_DIR": str(project),
           "PATH": os.environ.get("PATH", "") if with_path else ""}
    if os.environ.get("SYSTEMROOT"):
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    if plugin_data is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / hook)],
        input=json.dumps(payload), capture_output=True, text=True,
        timeout=60, env=env,
    )


# ------------------------------------------------------- the shared once-flag

def test_session_once_is_true_then_false(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert _engine.session_once("sess-a", "some-key") is True
    assert _engine.session_once("sess-a", "some-key") is False
    assert _engine.session_once("sess-b", "some-key") is True, "per session"
    assert _engine.session_once("sess-a", "other-key") is True, "per key"


def test_session_once_fails_open_without_a_data_dir(monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    assert _engine.session_once("sess-a", "some-key") is True
    assert _engine.session_once("sess-a", "some-key") is True


def test_session_once_fails_open_on_a_useless_session_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    assert _engine.session_once(None, "some-key") is True
    assert _engine.session_once("///", "some-key") is True
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert not written, "a hostile or empty session id must write nothing"


# ------------------------------------------- backend_tests timeout collapses

@pytest.fixture
def hanging_suite(tmp_path: Path) -> Path:
    """A repo whose configured 'suite' just sleeps past the timeout."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    interpreter = Path(sys.executable).as_posix()
    (repo / ".claude").mkdir()
    (repo / ".claude" / "engine.toml").write_text(
        f'[tests]\ninterpreter = "{interpreter}"\n'
        f'command = ["-c", "import time; time.sleep(5)"]\ntimeout = 1\n',
        encoding="utf-8",
    )
    return repo


def timeout_payload(repo: Path) -> dict:
    return {"session_id": "sess-hang",
            "tool_input": {"file_path": str(repo / "src" / "app" / "core.py")}}


def test_the_timeout_advisory_teaches_once_then_collapses(
    hanging_suite: Path, tmp_path: Path
) -> None:
    data = tmp_path / "plugin-data"
    data.mkdir()
    first = run_hook("backend_tests.py", timeout_payload(hanging_suite),
                     hanging_suite, plugin_data=data, with_path=True)
    second = run_hook("backend_tests.py", timeout_payload(hanging_suite),
                      hanging_suite, plugin_data=data, with_path=True)
    assert first.returncode == 0 and second.returncode == 0
    full = json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
    short = json.loads(second.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "usually a hang" in full, "the first emission must teach in full"
    assert "usually a hang" not in short
    assert "timed out again" in short, "collapsed, not silenced"
    assert "still not been shown green" in short
    assert len(short) < len(full) / 4


def test_the_timeout_advisory_stays_full_without_state(
    hanging_suite: Path,
) -> None:
    for _ in range(2):
        result = run_hook("backend_tests.py", timeout_payload(hanging_suite),
                          hanging_suite, plugin_data=None, with_path=True)
        out = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert "usually a hang" in out, "no state dir must mean the full advisory"


# --------------------------------------- dependency_audit missing pip-audit

needs_no_pip_audit = pytest.mark.skipif(
    importlib.util.find_spec("pip_audit") is not None,
    reason="pip-audit installed here; the missing-auditor path cannot fire",
)


@pytest.fixture
def manifest_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='x'\ndependencies=['requests']\n", encoding="utf-8"
    )
    return repo


def manifest_payload(repo: Path) -> dict:
    return {"session_id": "sess-dep",
            "tool_input": {"file_path": str(repo / "pyproject.toml")}}


@needs_no_pip_audit
def test_the_missing_auditor_nag_collapses_but_stays_honest(
    manifest_repo: Path, tmp_path: Path
) -> None:
    data = tmp_path / "plugin-data"
    data.mkdir()
    first = run_hook("dependency_audit.py", manifest_payload(manifest_repo),
                     manifest_repo, plugin_data=data)
    second = run_hook("dependency_audit.py", manifest_payload(manifest_repo),
                      manifest_repo, plugin_data=data)
    full = json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
    short = json.loads(second.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "pip-audit is not installed" in full
    assert "still not installed" in short
    assert "UNCHECKED" in short, "the collapsed line must keep the load-bearing word"
    assert len(short) < len(full)


@needs_no_pip_audit
def test_the_missing_auditor_nag_stays_full_without_state(
    manifest_repo: Path,
) -> None:
    for _ in range(2):
        result = run_hook("dependency_audit.py", manifest_payload(manifest_repo),
                          manifest_repo, plugin_data=None)
        out = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert "pip-audit is not installed" in out
