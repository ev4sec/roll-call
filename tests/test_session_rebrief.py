"""A rebuilt context is told what the ledgers hold, and only that.

**Why this file exists.** A compaction, a resume, or a fresh start is the
moment the founding failure recurs: whatever the engine had established with
the session is now whatever a summary kept. `session_rebrief.py` reads the
state the hooks wrote and hands it back. These tests pin the two halves of
that contract. It must name the consults still owed, the unreviewed agent
edits, and the queued claims, each from the file that holds it. And it must
say nothing at all when there is nothing, because a hook that repeats the
constitution on every start is the alarm that gets muted.

The owed-consult line is keyed by session id through the router's own state
file, so it is tested by firing the real router first and then the brief,
rather than by writing the state by hand: the seam between the two is the
thing most likely to drift.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
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

[[rule]]
id = "new-tests"
paths = ["tests/**"]
agents = ["test-strategist"]
level = "advised"
question = "What would still be broken?"
why = "Coverage failures cost the most."
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


def start(source: str = "compact", session: str = "s1") -> dict:
    return {"hook_event_name": "SessionStart", "source": source, "session_id": session}


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


# --------------------------------------------------------------- silence

def test_a_repository_with_no_state_hears_nothing(project: Path, data: Path) -> None:
    result = run("session_rebrief", start(), project, data)
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip()
    assert not result.stderr.strip()


def test_an_unconfigured_repository_hears_nothing(tmp_path: Path) -> None:
    result = run("session_rebrief", start(), tmp_path)
    assert result.returncode == 0
    assert not result.stdout.strip()
    assert not (tmp_path / ".claude").exists()


def test_garbage_on_stdin_is_survived(project: Path) -> None:
    result = run("session_rebrief", "{not json", project)
    assert result.returncode == 0
    assert not result.stdout.strip()


# ------------------------------------------------------------ owed consults

def test_an_owed_consult_from_earlier_in_the_session_is_named(project: Path, data: Path) -> None:
    blocked = edit(project, "src/app/models.py", data=data)
    assert blocked.returncode == 2, "fixture: the router should have demanded the consult"

    result = run("session_rebrief", start(), project, data)
    assert "[data-model] -> systems-architect" in result.stdout
    assert "routing.toml" in result.stdout, "the brief must point at the full text"
    assert "context was rebuilt (compact)" in result.stdout


def test_a_consult_that_landed_on_the_ledger_is_no_longer_owed(project: Path, data: Path) -> None:
    edit(project, "src/app/models.py", data=data)
    run("agent_watch", {"tool_input": {"subagent_type": "systems-architect"}}, project, data)
    (project / ".claude" / ".agent-ran").unlink()  # the commit guard's job, done by hand

    result = run("session_rebrief", start(), project, data)
    assert "[data-model]" not in result.stdout
    assert not result.stdout.strip(), "nothing owed and nothing pending means silence"


def test_another_sessions_state_is_not_this_sessions(project: Path, data: Path) -> None:
    edit(project, "src/app/models.py", session="other", data=data)
    result = run("session_rebrief", start(session="s1"), project, data)
    assert "[data-model]" not in result.stdout


def test_an_advised_rule_is_never_reported_as_owed(project: Path, data: Path) -> None:
    (project / "tests").mkdir()
    edit(project, "tests/test_x.py", data=data)
    result = run("session_rebrief", start(), project, data)
    assert "[new-tests]" not in result.stdout


def test_no_plugin_data_means_no_owed_line_and_no_crash(project: Path) -> None:
    edit(project, "src/app/models.py")
    result = run("session_rebrief", start(), project)
    assert result.returncode == 0
    assert "[data-model]" not in result.stdout


# --------------------------------------------------- marker and the queue

def test_unreviewed_agent_edits_are_named_with_their_files(project: Path, data: Path) -> None:
    (project / ".claude" / ".agent-ran").write_text(
        "10:00:00 security-engineer\tsrc/app/auth.py,src/app/session.py\n", encoding="utf-8")
    result = run("session_rebrief", start("resume"), project, data)
    assert "security-engineer" in result.stdout
    assert "src/app/auth.py, src/app/session.py" in result.stdout
    assert "(resume)" in result.stdout


def test_a_marker_whose_files_are_unknown_names_the_source_root(project: Path, data: Path) -> None:
    (project / ".claude" / ".agent-ran").write_text("10:00:00 security-engineer\n", encoding="utf-8")
    result = run("session_rebrief", start(), project, data)
    assert "touched the source root" in result.stdout


def test_a_marker_recording_no_changes_is_not_reported(project: Path, data: Path) -> None:
    (project / ".claude" / ".agent-ran").write_text("10:00:00 security-engineer\t-\n", encoding="utf-8")
    result = run("session_rebrief", start(), project, data)
    assert not result.stdout.strip()


def test_queued_claims_are_counted_by_seat(project: Path, data: Path) -> None:
    now = f"{time.time():.0f}"
    (project / ".claude" / ".pending-findings").write_text(
        f"{now}\tsecurity-engineer\tverified\t[verified] a\n"
        f"{now}\tsystems-architect\treasoned\t[reasoned] b\n"
        "not a row\n", encoding="utf-8")
    result = run("session_rebrief", start("startup"), project, data)
    assert "2 claims from security-engineer, systems-architect" in result.stdout
    assert ".pending-findings" in result.stdout


def test_recent_consults_ride_along_only_when_there_is_something_to_say(
    project: Path, data: Path,
) -> None:
    run("agent_watch", {"tool_input": {"subagent_type": "test-strategist"}}, project, data)
    (project / ".claude" / ".agent-ran").unlink()
    quiet = run("session_rebrief", start(), project, data)
    assert not quiet.stdout.strip(), "a consult alone is not state worth a brief"

    (project / ".claude" / ".pending-findings").write_text(
        f"{time.time():.0f}\ttest-strategist\tread\t[read] x\n", encoding="utf-8")
    spoken = run("session_rebrief", start(), project, data)
    assert "Already consulted: test-strategist" in spoken.stdout
