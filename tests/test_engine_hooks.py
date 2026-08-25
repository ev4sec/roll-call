"""The hooks themselves, exercised through the real process.

**Why this file exists.** Every other guard in the engine is enforced by a hook.
Nothing enforced the hooks. A hook that crashes on a payload shape, or that
silently no-ops because a config key was renamed, removes its guard and says
nothing, and the whole stack is built on the observation that a control which
fails silently is worse than no control.

The tests run each hook as a subprocess with a synthetic payload on stdin,
because that is exactly how the harness invokes them. Importing the module would
test something the harness never does.

**Each assertion has its negative pole.** A hook that fires on everything gets
muted within a day, so "stays silent when it should" is tested as carefully as
"fires when it should".

This file is portable and needs no edits at instantiation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"

ALL_HOOKS = sorted(p for p in HOOKS.glob("*.py") if not p.name.startswith("_"))


def run_hook(hook: Path, payload: object, project: Path, timeout: int = 60):
    """Invoke a hook the way the harness does: JSON on stdin, env for the root."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(hook)],
        input=text,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={"CLAUDE_PROJECT_DIR": str(project), "PATH": ""},
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A repo skeleton carrying the real `.claude/` config, with no source."""
    claude = tmp_path / ".claude"
    claude.mkdir()
    for name in ("routing.toml", "engine.toml"):
        source = ROOT / "templates" / name
        if source.is_file():
            (claude / name).write_bytes(source.read_bytes())
    return tmp_path


def test_the_hook_set_is_not_empty() -> None:
    """Negative pole for every parametrised test below."""
    assert ALL_HOOKS, "no hooks found; every test in this file would be vacuous"


@pytest.mark.parametrize("hook", ALL_HOOKS, ids=lambda p: p.stem)
def test_a_hook_survives_malformed_input(hook: Path, project: Path) -> None:
    """Garbage on stdin must never crash the session.

    A hook that raises leaves a traceback in the harness and, worse, takes its
    guard offline for that call. The publish guard is the deliberate exception:
    it fails *closed*, so it answers with a prompt rather than silence, but it
    still must not crash.
    """
    result = run_hook(hook, "this is not json at all", project)
    assert result.returncode == 0, (
        f"{hook.name} exited {result.returncode} on malformed input:\n{result.stderr}"
    )


@pytest.mark.parametrize("hook", ALL_HOOKS, ids=lambda p: p.stem)
def test_a_hook_survives_an_empty_payload(hook: Path, project: Path) -> None:
    result = run_hook(hook, {}, project)
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------- publish

def test_publish_guard_asks_on_a_package_upload(project: Path) -> None:
    result = run_hook(
        HOOKS / "publish_guard.py",
        {"tool_input": {"command": "twine upload dist/*"}},
        project,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    decision = payload["hookSpecificOutput"]["permissionDecision"]
    assert decision == "ask"


def test_publish_guard_fails_closed_on_an_unparseable_payload(project: Path) -> None:
    """An unknown state at a publish gate must mean "ask", never "proceed".

    This is the one hook whose failure mode is deliberately the opposite of the
    others: an error that silently returned 0 would let a publish through
    unprompted, which is exactly what the gate exists to prevent.
    """
    result = run_hook(HOOKS / "publish_guard.py", "{not json", project)
    assert result.returncode == 0
    assert result.stdout.strip(), "fail-closed guard produced no prompt"
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'work in progress'",
        "git stash push -u",
        "git status",
        "ls -la",
    ],
)
def test_publish_guard_stays_silent_on_local_work(command: str, project: Path) -> None:
    """**The negative pole, and the more important half.**

    `git stash push -u` is purely local and once prompted as "a push to GitHub".
    A false prompt trains the habit of approving without reading, on the one
    prompt that matters.
    """
    result = run_hook(HOOKS / "publish_guard.py", {"tool_input": {"command": command}}, project)
    assert result.returncode == 0
    assert not result.stdout.strip(), f"{command!r} produced a publish prompt"


# ------------------------------------------------------------------ scanning

def test_security_scan_blocks_a_real_finding(project: Path, tmp_path: Path) -> None:
    target = tmp_path / "danger.py"
    target.write_text("value = eval(user_input)\n", encoding="utf-8")
    result = run_hook(
        HOOKS / "security_scan.py",
        {"tool_input": {"file_path": str(target)}},
        project,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "py-eval" in payload["reason"]


def test_security_scan_honors_a_deliberate_suppression(project: Path, tmp_path: Path) -> None:
    """Every exception must be deliberate and greppable, not a switched-off scanner."""
    slug = "project"  # the default slug when engine.toml carries the template value
    conf = (project / ".claude" / "engine.toml")
    if conf.is_file():
        import tomllib
        with conf.open("rb") as fh:
            slug = tomllib.load(fh).get("project", {}).get("slug", slug)

    target = tmp_path / "allowed.py"
    target.write_text(
        f"value = eval(expr)  # {slug}: allow py-eval - sandboxed expression, see INV-4\n",
        encoding="utf-8",
    )
    result = run_hook(
        HOOKS / "security_scan.py",
        {"tool_input": {"file_path": str(target)}},
        project,
    )
    assert result.returncode == 0
    assert not result.stdout.strip(), "a suppressed finding still reported"


def test_security_scan_tolerates_documenting_the_pattern_it_forbids(
    project: Path, tmp_path: Path
) -> None:
    """A scanner that cannot tolerate its own documentation gets switched off.

    Triple-quoted strings are masked before scanning. The regex version of this
    masking once opened a fake block on a line that merely *mentioned* a triple
    quote and went blind to end of file, reporting clean. A false negative in
    the enforcement mechanism itself.
    """
    target = tmp_path / "documented.py"
    target.write_text(
        '"""Why eval(x) is banned here.\n\nBecause eval(x) executes anything.\n"""\n'
        "SAFE = 1\n",
        encoding="utf-8",
    )
    result = run_hook(
        HOOKS / "security_scan.py",
        {"tool_input": {"file_path": str(target)}},
        project,
    )
    assert result.returncode == 0
    assert not result.stdout.strip(), "docstring text tripped the scanner"


def test_security_scan_ignores_a_clean_file(project: Path, tmp_path: Path) -> None:
    target = tmp_path / "fine.py"
    target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    result = run_hook(
        HOOKS / "security_scan.py",
        {"tool_input": {"file_path": str(target)}},
        project,
    )
    assert not result.stdout.strip()


# ---------------------------------------------------------------- agent watch

def test_agent_watch_records_both_the_marker_and_the_ledger(project: Path) -> None:
    """Two files, two lifetimes. Merging them breaks one of the two guards.

    The marker answers "did an agent touch the tree since the last commit" and
    is cleared by the commit guard. The ledger is an append-only time series the
    consult router reads, and it must survive that clearing.
    """
    result = run_hook(
        HOOKS / "agent_watch.py",
        {"tool_input": {"subagent_type": "systems-architect"}},
        project,
    )
    assert result.returncode == 0

    marker = project / ".claude" / ".agent-ran"
    ledger = project / ".claude" / ".consults"
    assert marker.is_file(), "no marker written; the commit guard can never fire"
    assert ledger.is_file(), "no ledger written; the consult router sees no consults"

    line = ledger.read_text(encoding="utf-8").strip()
    name, _, stamp = line.partition("\t")
    assert name == "systems-architect"
    assert float(stamp) > 0, "ledger entry carries no usable timestamp"


def test_the_ledger_the_watcher_writes_is_the_ledger_the_router_reads(
    project: Path,
) -> None:
    """The two hooks agree on a format, and nothing else makes them agree.

    This is the seam where the mechanism would fail silently: the router would
    report every consult as owed, forever, and read as if nobody ever asked
    anyone.
    """
    run_hook(
        HOOKS / "agent_watch.py",
        {"tool_input": {"subagent_type": "systems-architect"}},
        project,
    )
    result = run_hook(
        HOOKS / "consult_router.py",
        {"tool_input": {"file_path": str(project / "src" / "PROJECT_SLUG" / "models.py")}},
        project,
    )
    assert result.returncode == 0, (
        "the router still owes a consult that agent_watch just recorded:\n"
        + result.stderr
    )


def test_unreviewed_agent_edits_stays_silent_without_a_marker(project: Path) -> None:
    """Most commits do not follow an agent. The window has to stay small."""
    result = run_hook(
        HOOKS / "unreviewed_agent_edits.py",
        {"tool_input": {"command": "git commit -m 'ordinary work'"}},
        project,
    )
    assert result.returncode == 0
    assert not result.stdout.strip()


# ------------------------------------------------------- the quiet majority

@pytest.mark.parametrize(
    "hook_name",
    ["backend_tests.py", "dependency_audit.py", "artifact_check.py", "security_scan.py"],
)
def test_the_heavy_hooks_no_op_on_an_irrelevant_edit(hook_name: str, project: Path) -> None:
    """Most edits match nothing, and the hooks must be cheap and quiet on those."""
    result = run_hook(
        HOOKS / hook_name,
        {"tool_input": {"file_path": str(project / "notes" / "scratch.txt")}},
        project,
    )
    assert result.returncode == 0
    assert not result.stdout.strip(), f"{hook_name} spoke about an unrelated text file"
