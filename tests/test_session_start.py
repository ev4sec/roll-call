"""The onboarding hook, which is the only thing that tells anyone to run init.

**Why this file exists.** `session_start.py` is the answer to a real hole: the
plugin installs once at user scope and is then live in every repository, but the
thing that makes it work is per project. Before this hook the only thing that
told a user to run `/roll-call:init` was the README, and an onboarding step that
depends on someone having read the documentation carefully is exactly the
assumption this engine exists to stop making.

**What has to be true, and why each one is a real failure mode.**

The offer must appear in a repository that has never been set up, or nobody
learns the command exists. It must then never appear again, because the plugin
is live in every repository the user opens and most of them are not projects
they want an engine in. A hook that asks every session is the alarm that cries
wolf, and this project has written down more than once that such an alarm gets
muted and takes the credible alarms down with it.

It must stay silent in a healthy project, because the operating procedure is
already loaded there and the hook has nothing to add. It must speak in a broken
one, every time, because a half-built setup is not a user who has not started.

The plural case is here because it was a genuine defect, caught only by running
the thing: with two files missing the message read "routing.toml, agents **is**
missing". Small, and read by someone already confused about why their setup is
half-built.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "session_start.py"


def fire(project: Path, data: Path | None = None) -> dict:
    """Invoke the hook the way the harness does. Returns parsed stdout, or {}."""
    env = {"CLAUDE_PROJECT_DIR": str(project), "PATH": ""}
    if data is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(data)
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK)],
        input=json.dumps({"hook_event_name": "SessionStart"}),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 0, f"hook must never block: {proc.stderr}"
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def configured(root: Path, *, routing: bool = True, agents: bool = True) -> Path:
    claude = root / ".claude"
    (claude / "agents").mkdir(parents=True) if agents else claude.mkdir(parents=True)
    (claude / "engine.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    if routing:
        (claude / "routing.toml").write_text("[settings]\n", encoding="utf-8")
    return root


def test_a_fresh_project_is_offered_init(tmp_path: Path) -> None:
    out = fire(tmp_path, tmp_path / "data")
    assert "/roll-call:init" in out["systemMessage"]


def test_the_offer_is_made_once_and_never_again(tmp_path: Path) -> None:
    project, data = tmp_path / "repo", tmp_path / "data"
    project.mkdir()
    assert fire(project, data), "first session must offer"
    assert fire(project, data) == {}, "second session must be silent"
    assert fire(project, data) == {}, "and stay silent"


def test_a_different_project_is_still_offered(tmp_path: Path) -> None:
    """The record is per repository. Silencing one must not silence the rest."""
    data = tmp_path / "data"
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    fire(first, data)
    assert fire(second, data), "a second repo has not been offered yet"


def test_a_healthy_project_says_nothing(tmp_path: Path) -> None:
    assert fire(configured(tmp_path), tmp_path / "data") == {}


@pytest.mark.parametrize(
    ("routing", "agents", "verb", "named"),
    [
        (False, True, " is missing", ".claude/routing.toml"),
        (True, False, " is missing", ".claude/agents"),
        (False, False, " are missing", ".claude/routing.toml, .claude/agents"),
    ],
)
def test_an_incomplete_project_names_what_is_missing(
    tmp_path: Path, routing: bool, agents: bool, verb: str, named: str
) -> None:
    """Plural agreement included, because it was wrong and nothing caught it."""
    project = tmp_path / "repo"
    project.mkdir()
    configured(project, routing=routing, agents=agents)
    message = fire(project, tmp_path / "data")["systemMessage"]
    assert named + verb in message
    assert "/roll-call:doctor" in message


def test_an_incomplete_project_is_told_every_session(tmp_path: Path) -> None:
    """Unlike the offer. A damaged setup is worth repeating until it is fixed."""
    project, data = tmp_path / "repo", tmp_path / "data"
    project.mkdir()
    configured(project, routing=False)
    assert fire(project, data)
    assert fire(project, data), "a broken setup does not get to go quiet"


def test_the_ignore_file_silences_everything(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".roll-call-ignore").touch()
    assert fire(tmp_path, tmp_path / "data") == {}


def test_no_project_dir_means_no_opinion(tmp_path: Path) -> None:
    """Without the variable there is no way to know which repo this is.

    Guessing would mean offering init for whatever directory the last tool call
    happened to leave behind, which is how a hook earns its way into being muted.
    """
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK)],
        input="{}",
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": ""},
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_garbage_on_stdin_is_survived(tmp_path: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK)],
        input="not json at all",
        capture_output=True,
        text=True,
        timeout=30,
        env={"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": ""},
    )
    assert proc.returncode == 0


def test_the_record_does_not_leak_a_list_of_repositories(tmp_path: Path) -> None:
    """Stamps are hashed.

    A plain-text directory of every repository on the machine is not something a
    plugin should leave behind in a shared data directory.
    """
    project, data = tmp_path / "secret-client-work", tmp_path / "data"
    project.mkdir()
    fire(project, data)
    stamps = list((data / "offered").iterdir())
    assert stamps, "the offer must be recorded"
    assert all("secret-client-work" not in p.name for p in stamps)
