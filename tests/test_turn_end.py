"""The turn ends, and the session is told what the router is still owed.

`turn_end.py` is the reminder at the moment the router's block has scrolled
out of view. It reuses the rebrief hook's reader, so these tests fire the real
router first and then the hook, the same way `test_session_rebrief.py` does:
the seam between the router's state file and the reader is the thing most
likely to drift. It must never block the stop, and it must say nothing when
nothing is owed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"

ROUTING = """
[settings]
fresh_hours = 24

[[rule]]
id = "data-model"
paths = ["src/app/models.py"]
agents = ["systems-architect"]
level = "required"
question = "State the field."
why = "Schema changes are load-bearing."
"""


def run(hook: str, payload: object, project: Path, data: Path | None = None):
    env = {"CLAUDE_PROJECT_DIR": str(project), "PATH": ""}
    if data is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(data)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / f"{hook}.py")],
        input=text, capture_output=True, text=True, timeout=60, env=env,
    )


def stop(session: str = "s1") -> dict:
    return {"hook_event_name": "Stop", "session_id": session, "stop_hook_active": False}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    (claude / "agents").mkdir(parents=True)
    (claude / "engine.toml").write_text(
        "[project]\nname = 'x'\nsource_root = 'src'\n", encoding="utf-8")
    (claude / "routing.toml").write_text(ROUTING, encoding="utf-8")
    return tmp_path


@pytest.fixture
def data(tmp_path: Path) -> Path:
    store = tmp_path / "plugin-data"
    store.mkdir()
    return store


def edit(project: Path, rel: str, session: str = "s1", data: Path | None = None):
    return run("consult_router",
               {"tool_input": {"file_path": str(project / rel)}, "session_id": session},
               project, data)


def test_nothing_owed_means_silence(project: Path, data: Path) -> None:
    result = run("turn_end", stop(), project, data)
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip()
    assert not result.stderr.strip()


def test_an_unconfigured_repository_hears_nothing(tmp_path: Path) -> None:
    result = run("turn_end", stop(), tmp_path)
    assert result.returncode == 0
    assert not result.stdout.strip()
    assert not (tmp_path / ".claude").exists()


def test_garbage_on_stdin_is_survived(project: Path) -> None:
    result = run("turn_end", "{not json", project)
    assert result.returncode == 0
    assert not result.stdout.strip()


def test_an_owed_consult_is_named_as_context_and_never_as_a_block(project: Path, data: Path) -> None:
    blocked = edit(project, "src/app/models.py", data=data)
    assert blocked.returncode == 2, "fixture: the router should have demanded the consult"

    result = run("turn_end", stop(), project, data)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "decision" not in out, "the hook must never force a continuation"
    context = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert "[data-model] -> systems-architect" in context
    assert "routing.toml" in context


def test_a_consult_that_finished_clears_it(project: Path, data: Path) -> None:
    edit(project, "src/app/models.py", data=data)
    run("agent_watch", {"hook_event_name": "SubagentStop",
                        "agent_type": "systems-architect"}, project, data)

    result = run("turn_end", stop(), project, data)
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip()


def test_another_sessions_debt_is_not_this_ones(project: Path, data: Path) -> None:
    edit(project, "src/app/models.py", session="other", data=data)
    result = run("turn_end", stop(session="s1"), project, data)
    assert not result.stdout.strip()
