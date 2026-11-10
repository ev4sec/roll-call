"""One process per event, and nothing lost in the merge.

Four events used to start two hooks each. `pre_shell.py`, `post_edit.py`,
`agent_stop.py`, and `session_open.py` each run a pair in one process. These
tests pin what the merge must not change: the publish guard still fails
closed, the router's exit code still carries the demand, a scan finding is
not lost when the router speaks first, and each half of a pair still reports
when the other has nothing to say.

The second half covers the rest of the same release: the shim's early exit
in a repository that never ran init, the commit guard reading the subcommand
instead of the word, the ledger's tail read, the audit running once per
ecosystem, and bandit running once per batch.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import time
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
paths = ["src/models.py"]
agents = ["systems-architect"]
level = "required"
question = "State the field."
why = "A shipped column is a migration."
"""

ENGINE = """
[project]
name = "Merged"
slug = "merged"
source_root = "src"

[tests]
dir = "checks"

[dependencies]
enabled = true

[artifact]
enabled = false
"""

# Spelled in pieces so this file does not carry the pattern the scan forbids.
DANGER = "value = ev" + "al(user_input)\n"


def run(name: str, payload: object, project: Path, **extra: str):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / f"{name}.py")],
        input=text, capture_output=True, text=True, timeout=120,
        env=hook_env(project, **extra), cwd=str(project),
    )


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HOOKS))
    try:
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(HOOKS))
    # The shared loader caches its config for the life of a process, which
    # for a hook is one event and for this suite is every test in the file.
    engine = sys.modules.get("_engine")
    if engine is not None:
        engine._cache = None
    return mod


@pytest.fixture
def project(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    (claude / "agents").mkdir(parents=True)
    (claude / "agents" / "systems-architect.md").write_text("seat\n", encoding="utf-8")
    (claude / "engine.toml").write_text(ENGINE, encoding="utf-8")
    (claude / "routing.toml").write_text(ROUTING, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "models.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ pre_shell

def ask_reason(result) -> str:
    out = json.loads(result.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "ask"
    return out["permissionDecisionReason"]


def test_pre_shell_asks_once_for_a_publish(project: Path) -> None:
    result = run("pre_shell", {"tool_input": {"command": "twine upload dist/*"}}, project)
    assert result.returncode == 0
    assert "package upload" in ask_reason(result)


def test_pre_shell_is_silent_on_local_work(project: Path) -> None:
    for command in ("ls", "git status", "git commit -m x", "git stash push -u"):
        result = run("pre_shell", {"tool_input": {"command": command}}, project)
        assert result.returncode == 0
        assert not result.stdout.strip(), command


def test_pre_shell_fails_closed_on_an_unparseable_payload(project: Path) -> None:
    result = run("pre_shell", "{not json", project)
    assert result.returncode == 0
    assert "could not parse" in ask_reason(result)


def test_pre_shell_only_ever_asks(project: Path) -> None:
    """The directory reads this hook's possible answers. There is one."""
    for name in ("pre_shell", "publish_guard", "unreviewed_agent_edits"):
        source = (HOOKS / f"{name}.py").read_text(encoding="utf-8")
        for answer in ('"al' + 'low"', '"de' + 'ny"'):
            assert answer not in source, f"{name}.py can answer {answer}"


def test_pre_shell_carries_both_prompts_in_one_answer(project: Path) -> None:
    """A commit and a publish in one command: one prompt, both reasons."""
    subprocess.run(["git", "init", "-q", str(project)], check=True, timeout=60)  # noqa: S603, S607
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(project), "config", key, value],  # noqa: S603, S607
                       check=True, timeout=60)
    subprocess.run(["git", "-C", str(project), "add", "src/models.py"],  # noqa: S603, S607
                   check=True, timeout=60)
    subprocess.run(["git", "-C", str(project), "commit", "-q", "-m", "base"],  # noqa: S603, S607
                   check=True, timeout=60)
    (project / "src" / "models.py").write_text("x = 2\n", encoding="utf-8")
    (project / ".claude" / ".agent-ran").write_text("10:00:00 systems-architect\n",
                                                    encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / "pre_shell.py")],
        input=json.dumps({"tool_input": {"command": "git commit -am x && npm publish"}}),
        capture_output=True, text=True, timeout=120,
        env=hook_env(project, inherit_path=True), cwd=str(project),
    )
    reason = ask_reason(result)
    assert "package upload" in reason
    assert "advisory agent ran" in reason
    assert reason.index("package upload") < reason.index("advisory agent ran")
    assert not (project / ".claude" / ".agent-ran").exists()


# ------------------------------------------------------------ the commit guard

@pytest.mark.parametrize("command", [
    "git commit -m x",
    "git -C sub commit -m x",
    'git -c user.name="A B" commit -m x',
    "git add -A && git commit -m 'fix; more'",
    "git-commit -m x",
    "GIT COMMIT -m x",
])
def test_a_commit_is_recognized(command: str) -> None:
    assert load("unreviewed_agent_edits").is_git_commit(command), command


@pytest.mark.parametrize("command", [
    "git log --grep=commit",
    "git diff HEAD -- docs/commit.md",
    "git show --format=%H commit-ish",
    "git status",
    "git commit-tree abc",
    "echo commit",
])
def test_a_command_that_only_mentions_commit_is_not_one(command: str) -> None:
    assert not load("unreviewed_agent_edits").is_git_commit(command), command


def test_a_read_only_git_command_does_not_spend_the_marker(project: Path) -> None:
    """Firing clears the marker, so a false match used the one prompt the real
    commit needed."""
    marker = project / ".claude" / ".agent-ran"
    marker.write_text("10:00:00 systems-architect\n", encoding="utf-8")
    result = run("pre_shell", {"tool_input": {"command": "git log --grep=commit"}}, project)
    assert not result.stdout.strip()
    assert marker.exists()


def test_the_push_parser_still_reads_a_quoted_option() -> None:
    engine = load("_engine")
    assert engine.git_subcommand(' -c user.name="A B" push origin main') == (
        "push", ["origin", "main"])
    assert engine.git_subcommand(" --no-pager") is None
    assert engine.git_subcommand(' stash push -m "unbalanced') == (
        "stash", ["push", "-m", '"unbalanced'])


# ------------------------------------------------------------------ post_edit

def edit(project: Path, rel: str, session: str = "s1") -> dict:
    return {"tool_name": "Edit", "session_id": session,
            "tool_input": {"file_path": str(project / rel)}}


def test_post_edit_blocks_with_the_routers_message(project: Path) -> None:
    result = run("post_edit", edit(project, "src/models.py"), project)
    assert result.returncode == 2
    assert "CONSULT OWED" in result.stderr
    assert "systems-architect" in result.stderr


def test_post_edit_reports_a_scan_finding_when_nothing_is_routed(project: Path) -> None:
    (project / "src" / "other.py").write_text(DANGER, encoding="utf-8")
    result = run("post_edit", edit(project, "src/other.py"), project)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["decision"] == "block"
    assert "py-eval" in out["reason"]


def test_post_edit_keeps_the_scan_finding_when_the_router_blocks(project: Path) -> None:
    """Exit 2 is read from stderr. A finding printed beside it would be lost."""
    (project / "src" / "models.py").write_text(DANGER, encoding="utf-8")
    result = run("post_edit", edit(project, "src/models.py"), project)
    assert result.returncode == 2
    assert "CONSULT OWED" in result.stderr
    assert "py-eval" in result.stderr
    assert not result.stdout.strip()


def test_post_edit_is_silent_on_a_clean_unrouted_edit(project: Path) -> None:
    (project / "src" / "other.py").write_text("x = 1\n", encoding="utf-8")
    result = run("post_edit", edit(project, "src/other.py"), project)
    assert result.returncode == 0
    assert not result.stdout.strip()
    assert not result.stderr.strip()


def test_the_configured_test_directory_relaxes_the_scan(project: Path) -> None:
    """`[tests] dir` is "checks" here; a fixture secret there is a warning."""
    (project / "checks").mkdir()
    target = project / "checks" / "fixture.py"
    target.write_text('password = "hunter2hunter2"\n', encoding="utf-8")
    result = run("post_edit", edit(project, "checks/fixture.py"), project)
    out = json.loads(result.stdout)
    assert "decision" not in out
    assert "py-secret-literal" in out["hookSpecificOutput"]["additionalContext"]


# ----------------------------------------------------------------- agent_stop

def test_agent_stop_stamps_the_ledger_and_queues_the_claims(project: Path) -> None:
    payload = {"hook_event_name": "SubagentStop", "agent_type": "systems-architect",
               "agent_id": "a1", "last_assistant_message": "[verified] it runs"}
    result = run("agent_stop", payload, project)
    assert result.returncode == 0
    assert not result.stdout.strip()
    ledger = (project / ".claude" / ".consults").read_text(encoding="utf-8")
    assert ledger.startswith("systems-architect\t")
    pending = (project / ".claude" / ".pending-findings").read_text(encoding="utf-8")
    assert "\tsystems-architect\tverified\t" in pending
    # And the router now reads that consult as fresh.
    routed = run("post_edit", edit(project, "src/models.py"), project)
    assert routed.returncode == 0, routed.stderr


def test_agent_stop_records_a_helper_on_the_ledger_only(project: Path) -> None:
    payload = {"hook_event_name": "SubagentStop", "agent_type": "Explore",
               "agent_id": "a2", "last_assistant_message": "[verified] it runs"}
    run("agent_stop", payload, project)
    assert (project / ".claude" / ".consults").is_file()
    assert not (project / ".claude" / ".pending-findings").exists()


# --------------------------------------------------------------- session_open

def start(source: str = "startup", session: str = "s1") -> dict:
    return {"hook_event_name": "SessionStart", "source": source, "session_id": session}


def test_session_open_offers_init_once_and_only_on_startup(tmp_path: Path) -> None:
    data = tmp_path / "data"
    repo = tmp_path / "repo"
    repo.mkdir()
    resumed = run("session_open", start("resume"), repo, CLAUDE_PLUGIN_DATA=str(data))
    assert not resumed.stdout.strip(), "a resume is not the moment to offer init"
    first = run("session_open", start(), repo, CLAUDE_PLUGIN_DATA=str(data))
    assert "/roll-call:init" in json.loads(first.stdout)["systemMessage"]
    second = run("session_open", start(), repo, CLAUDE_PLUGIN_DATA=str(data))
    assert not second.stdout.strip()


def test_session_open_rebriefs_in_plain_text(project: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    blocked = run("post_edit", edit(project, "src/models.py"), project,
                  CLAUDE_PLUGIN_DATA=str(data))
    assert blocked.returncode == 2
    result = run("session_open", start("compact"), project, CLAUDE_PLUGIN_DATA=str(data))
    assert result.stdout.startswith("roll-call: the context was rebuilt (compact)")
    assert "[data-model] -> systems-architect" in result.stdout


def test_session_open_says_both_things_in_one_object(project: Path, tmp_path: Path) -> None:
    """A damaged setup with live ledgers: the notice and the brief together."""
    data = tmp_path / "data"
    (project / ".claude" / ".pending-findings").write_text(
        "1\tsystems-architect\tverified\tit runs\n", encoding="utf-8")
    shutil.rmtree(project / ".claude" / "agents")
    result = run("session_open", start(), project, CLAUDE_PLUGIN_DATA=str(data))
    out = json.loads(result.stdout)
    assert "incomplete" in out["systemMessage"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "awaits a verdict" in out["hookSpecificOutput"]["additionalContext"]


def test_session_open_is_silent_in_a_healthy_quiet_repository(project: Path) -> None:
    result = run("session_open", start(), project)
    assert result.returncode == 0
    assert not result.stdout.strip()


# -------------------------------------------------------- the shim's early exit

def _tattling_python(shims: Path, witness: Path) -> None:
    """A `python` and `python3` that record being started and then defer."""
    real = Path(sys.executable).as_posix()
    for name in ("python", "python3"):
        script = shims / name
        script.write_text(
            f'#!/bin/sh\necho started >> "{witness.as_posix()}"\nexec "{real}" "$@"\n',
            encoding="utf-8", newline="\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)


def _shim(hook: str, project: Path, shims: Path, payload: dict):
    sh = shutil.which("sh")
    assert sh is not None
    env = hook_env(project, PATH=os.pathsep.join([str(shims), str(Path(sh).parent)]), OS="")
    return subprocess.run(  # noqa: S603
        [sh, str(HOOKS / "run.sh"), hook],
        input=json.dumps(payload), capture_output=True, text=True, timeout=120, env=env,
    )


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_the_shim_starts_no_interpreter_where_init_never_ran(tmp_path: Path) -> None:
    shims = tmp_path / "shims"
    shims.mkdir()
    witness = tmp_path / "witness.txt"
    _tattling_python(shims, witness)
    repo = tmp_path / "repo"
    repo.mkdir()
    for hook in ("pre_shell", "post_edit", "post_batch", "agent_stop", "turn_end"):
        result = _shim(hook, repo, shims, {"tool_input": {"command": "git push origin main"}})
        assert result.returncode == 0
        assert not result.stdout.strip()
    assert not witness.exists(), "an interpreter was started in an unconfigured repository"


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_the_shim_still_runs_the_session_hook_where_init_never_ran(tmp_path: Path) -> None:
    """Offering init in a repository with no config is that hook's whole job."""
    shims = tmp_path / "shims"
    shims.mkdir()
    witness = tmp_path / "witness.txt"
    _tattling_python(shims, witness)
    repo = tmp_path / "repo"
    repo.mkdir()
    result = _shim("session_open", repo, shims, start())
    assert "/roll-call:init" in result.stdout
    assert witness.exists()


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_the_shim_runs_the_guard_in_a_configured_repository(
    project: Path, tmp_path: Path,
) -> None:
    shims = tmp_path / "shims"
    shims.mkdir()
    witness = tmp_path / "witness.txt"
    _tattling_python(shims, witness)
    result = _shim("pre_shell", project, shims, {"tool_input": {"command": "npm publish"}})
    assert "package upload" in ask_reason(result)
    (project / ".claude" / ".roll-call-ignore").write_text("", encoding="utf-8")
    witness.unlink()
    quiet = _shim("pre_shell", project, shims, {"tool_input": {"command": "npm publish"}})
    assert not quiet.stdout.strip()
    assert not witness.exists(), "an opted-out repository still started an interpreter"


# ------------------------------------------------------------ the ledger tail

def test_freshness_is_read_from_the_end_of_a_long_ledger(project: Path) -> None:
    router = load("consult_router")
    ledger = project / ".claude" / ".consults"
    old = time.time() - 90 * 24 * 3600
    filler = "".join(f"old-seat\t{old:.0f}\n" for _ in range(8000))
    assert len(filler) > router.LEDGER_TAIL_BYTES * 2
    ledger.write_text(filler + f"systems-architect\t{time.time():.0f}\n", encoding="utf-8")
    assert router._fresh_consults(project, 24) == {"systems-architect"}
    required, _ = router.owed("src/models.py", project)
    assert required == []


def test_a_short_ledger_is_read_whole(project: Path) -> None:
    router = load("consult_router")
    now = time.time()
    (project / ".claude" / ".consults").write_text(
        f"first-seat\t{now:.0f}\nsecond-seat\t{now:.0f}\n", encoding="utf-8")
    assert router._fresh_consults(project, 24) == {"first-seat", "second-seat"}


# ------------------------------------------------------- the batch, once each

def batch(project: Path, *rels: str) -> dict:
    return {"hook_event_name": "PostToolBatch", "session_id": "s1",
            "tool_calls": [{"tool_name": "Edit", "tool_use_id": f"t{i}",
                            "tool_input": {"file_path": str(project / rel)},
                            "tool_response": "ok"} for i, rel in enumerate(rels)]}


def test_a_manifest_and_its_lockfile_are_audited_once(
    project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("pyproject.toml", "uv.lock", "package.json", "package-lock.json"):
        (project / name).write_text("", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    mod = load("post_batch")
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(mod.dependency_audit, "audit",
                        lambda repo, eco, basename, session: calls.append((eco, basename)))
    monkeypatch.setattr(mod.security_scan, "bandit_batch", lambda paths: None)
    mod.run(batch(project, "pyproject.toml", "uv.lock", "package.json", "package-lock.json"))
    assert calls == [("python", "pyproject.toml"), ("node", "package.json")]


def test_a_refused_package_is_looked_for_in_every_manifest(
    project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = project / ".claude" / "engine.toml"
    engine.write_text(
        ENGINE.replace("[dependencies]\n", '[dependencies]\nbanned = ["leftpad"]\n'),
        encoding="utf-8")
    (project / "pyproject.toml").write_text("", encoding="utf-8")
    (project / "requirements.txt").write_text("leftpad==1.0\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    mod = load("post_batch")
    monkeypatch.setattr(mod.dependency_audit, "audit", lambda *a: None)
    monkeypatch.setattr(mod.security_scan, "bandit_batch", lambda paths: None)
    out = mod.run(batch(project, "pyproject.toml", "requirements.txt"))
    assert out is not None
    assert "refused-dependency" in out["hookSpecificOutput"]["additionalContext"]


def test_a_failing_lane_does_not_take_the_other_lanes_report(
    project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (project / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    mod = load("post_batch")

    def boom(paths, session):
        raise RuntimeError("lane fell over")

    monkeypatch.setattr(mod, "tree_lane", boom)
    monkeypatch.setattr(mod.dependency_audit, "audit",
                        lambda *a: {"systemMessage": "audit spoke"})
    monkeypatch.setattr(mod.security_scan, "bandit_batch", lambda paths: None)
    out = mod.run(batch(project, "pyproject.toml"))
    assert out is not None
    assert "audit spoke" in out["systemMessage"]
    assert "could not run" in out["systemMessage"]


def test_bandit_runs_once_per_batch_with_tests_apart(
    project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (project / "checks").mkdir()
    for rel in ("src/a.py", "src/b.py", "checks/c.py", "src/notes.md"):
        (project / rel).write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    scan = load("security_scan")
    launches: list[tuple[list[str], bool]] = []

    def fake(paths, is_test=False, template=""):
        launches.append(([Path(p).name for p in paths], is_test))
        return [f"{Path(p).name} L1: [B000] finding (LOW)" for p in paths]

    monkeypatch.setattr(scan, "bandit_lines", fake)
    out = scan.bandit_batch([str(project / rel) for rel in
                             ("src/a.py", "src/b.py", "checks/c.py", "src/notes.md",
                              "src/missing.py")])
    assert launches == [(["a.py", "b.py"], False), (["c.py"], True)]
    assert "3 item(s)" in out["systemMessage"]
    assert "decision" not in out


def test_the_per_edit_scan_does_not_start_bandit(
    project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = project / "src" / "other.py"
    target.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    scan = load("security_scan")
    started: list[str] = []
    monkeypatch.setattr(scan, "bandit_lines",
                        lambda paths, **kw: started.append("x") or [])
    assert scan.check({"tool_input": {"file_path": str(target)}}) is None
    assert started == []
    scan.check({"tool_input": {"file_path": str(target)}}, with_bandit=True)
    assert started == ["x"]
