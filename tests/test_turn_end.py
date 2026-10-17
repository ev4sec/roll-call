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
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import hook_env

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


def run(hook: str, payload: object, project: Path, data: Path | None = None,
        with_git: bool = False):
    env = hook_env(project, inherit_path=with_git)
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


# ------------------------------------------------------- the tree, not the memory

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _git(project: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=project, capture_output=True, text=True, timeout=60, check=True,
    )


@pytest.fixture
def committed(project: Path) -> Path:
    """The routed fixture as a git repository with a clean HEAD."""
    (project / "src" / "app").mkdir(parents=True)
    (project / "src" / "app" / "models.py").write_text("x = 1\n", encoding="utf-8")
    _git(project, "init", "-q")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "base")
    return project


@needs_git
def test_a_routed_file_changed_outside_the_editor_is_named_once(
    committed: Path, tmp_path: Path,
) -> None:
    """The router never saw this change; the tree did."""
    data = tmp_path / "data"
    (committed / "src" / "app" / "models.py").write_text("x = 2\n", encoding="utf-8")

    first = run("turn_end", stop(), committed, data, with_git=True)
    assert first.returncode == 0, first.stderr
    context = json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "changed outside the editor tools" in context
    assert "[data-model] -> systems-architect (src/app/models.py)" in context

    # Named once per session: the next turn is quiet about the same change.
    second = run("turn_end", stop(), committed, data, with_git=True)
    assert not second.stdout.strip(), second.stdout

    # A new session says it again.
    third = run("turn_end", stop("s2"), committed, data, with_git=True)
    assert "[data-model]" in third.stdout


@needs_git
def test_an_untracked_routed_file_counts_too(committed: Path, tmp_path: Path) -> None:
    (committed / ".claude" / "routing.toml").write_text(
        ROUTING.replace('paths = ["src/app/models.py"]', 'paths = ["src/app/**"]'),
        encoding="utf-8")
    (committed / "src" / "app" / "schema.py").write_text("s = 1\n", encoding="utf-8")
    result = run("turn_end", stop(), committed, tmp_path / "data", with_git=True)
    assert "(src/app/schema.py)" in result.stdout


@needs_git
def test_a_fresh_consult_satisfies_the_tree_check(committed: Path, tmp_path: Path) -> None:
    import time
    (committed / "src" / "app" / "models.py").write_text("x = 2\n", encoding="utf-8")
    (committed / ".claude" / ".consults").write_text(
        f"systems-architect\t{time.time():.0f}\n", encoding="utf-8")
    result = run("turn_end", stop(), committed, tmp_path / "data", with_git=True)
    assert not result.stdout.strip(), result.stdout


@needs_git
def test_a_rule_the_router_already_fired_is_not_said_twice(
    committed: Path, tmp_path: Path,
) -> None:
    """The router's own demand is reported from its state; the tree check must
    not repeat it under the second heading."""
    data = tmp_path / "data"
    target = committed / "src" / "app" / "models.py"
    target.write_text("x = 2\n", encoding="utf-8")
    run("consult_router", {"tool_input": {"file_path": str(target)}, "session_id": "s1"},
        committed, data)
    result = run("turn_end", stop(), committed, data, with_git=True)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "the router demanded" in context
    assert "changed outside the editor tools" not in context


def test_without_git_the_tree_check_is_silent(project: Path, tmp_path: Path) -> None:
    (project / "src" / "app").mkdir(parents=True)
    (project / "src" / "app" / "models.py").write_text("x = 1\n", encoding="utf-8")
    result = run("turn_end", stop(), project, tmp_path / "data")
    assert result.returncode == 0
    assert not result.stdout.strip()


def test_a_router_demand_is_reminded_at_one_turn_end_per_session(
    project: Path, data: Path,
) -> None:
    """Stop-hook context is answered as feedback, so a reminder at every turn
    end became a forced continuation. Once per session, then the router and
    the rebrief carry it."""
    target = project / "src" / "app" / "models.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    run("consult_router", {"tool_input": {"file_path": str(target)}, "session_id": "s1"},
        project, data)
    first = run("turn_end", stop(), project, data)
    assert "[data-model] -> systems-architect" in first.stdout
    second = run("turn_end", stop(), project, data)
    assert not second.stdout.strip(), second.stdout
    # The rebrief still carries the debt into a rebuilt context.
    rebrief = run("session_rebrief",
                  {"hook_event_name": "SessionStart", "source": "compact", "session_id": "s1"},
                  project, data)
    assert "[data-model] -> systems-architect" in rebrief.stdout
    # A new session is reminded again.
    again = run("turn_end", stop("s2"), project, data)
    assert not again.stdout.strip(), "s2 never had the router fire, so nothing is owed to it"
