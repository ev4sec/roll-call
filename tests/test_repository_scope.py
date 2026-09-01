"""The guards belong only to repositories that asked for them.

The plugin installs at user scope, so its hooks are present in every
repository the user opens. Until `/roll-call:init` has written
`.claude/engine.toml`, every hook must stay silent, and an empty
`.claude/.roll-call-ignore` must keep them silent afterward. These tests run
each hook the way the harness does, with a payload that would make it speak in
a configured repository, and assert that it says nothing in an unconfigured
one.

The second half covers the ecosystem paths: a non-Python test command, a Node
manifest, the ledger gitignore init writes, the relaxed scan severities in
test files, and the pre/post agent snapshot that scopes the commit prompt.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
SCAFFOLD = ROOT / "scripts" / "scaffold.py"


def run_hook(name: str, payload: object, project: Path, env_extra: dict | None = None,
             inherit_path: bool = False):
    env = {"CLAUDE_PROJECT_DIR": str(project), "PATH": os.environ.get("PATH", "") if inherit_path else ""}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    env.update(env_extra or {})
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(HOOKS / f"{name}.py")],
        input=text, capture_output=True, text=True, timeout=120, env=env,
        cwd=str(project),
    )


def configure(project: Path) -> None:
    claude = project / ".claude"
    claude.mkdir(exist_ok=True)
    for name in ("routing.toml", "engine.toml"):
        (claude / name).write_bytes((ROOT / "templates" / name).read_bytes())


def firing_payloads(project: Path) -> dict[str, dict]:
    """A payload per hook that makes it speak in a configured repository."""
    (project / "src").mkdir(exist_ok=True)
    danger = project / "src" / "danger.py"
    danger.write_text("value = eval(user_input)\n", encoding="utf-8")  # project: allow py-eval - fixture text the scan must flag
    (project / "package.json").write_text('{"name": "x", "dependencies": {"left-pad": "1.3.0"}}',
                                          encoding="utf-8")
    (project / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n',
                                            encoding="utf-8")
    return {
        "security_scan": {"tool_input": {"file_path": str(danger)}},
        "backend_tests": {"tool_input": {"file_path": str(danger)}},
        "dependency_audit": {"tool_input": {"file_path": str(project / "package.json")}},
        "artifact_check": {"tool_input": {"file_path": str(project / "pyproject.toml")}},
        "consult_router": {"tool_input": {"file_path": str(project / "src" / "PROJECT_SLUG" / "models.py")}},
        "publish_guard": {"tool_input": {"command": "git push origin main"}},
        "unreviewed_agent_edits": {"tool_input": {"command": "git commit -m x"}},
        "agent_watch": {"tool_input": {"subagent_type": "systems-architect"}, "tool_use_id": "t1"},
        "agent_snapshot": {"tool_input": {"subagent_type": "systems-architect"}, "tool_use_id": "t1"},
    }


HOOK_NAMES = sorted(
    p.stem for p in HOOKS.glob("*.py") if not p.name.startswith("_") and p.stem != "session_start"
)


def test_every_hook_has_a_firing_payload(tmp_path: Path) -> None:
    """Negative pole: a hook missing from the table below is untested here."""
    assert set(firing_payloads(tmp_path)) == set(HOOK_NAMES)


@pytest.mark.parametrize("hook", HOOK_NAMES)
def test_an_unconfigured_repository_hears_nothing(hook: str, tmp_path: Path) -> None:
    payloads = firing_payloads(tmp_path)
    data = tmp_path / "plugin-data"
    data.mkdir()
    result = run_hook(hook, payloads[hook], tmp_path, {"CLAUDE_PLUGIN_DATA": str(data)})
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip(), f"{hook} spoke in a repository that never ran init"
    assert not result.stderr.strip(), f"{hook} complained in a repository that never ran init"
    assert not (tmp_path / ".claude").exists(), f"{hook} created .claude/ uninvited"
    assert not list(data.rglob("*")), f"{hook} wrote plugin state for an unconfigured repository"


@pytest.mark.parametrize("hook", HOOK_NAMES)
def test_an_opted_out_repository_hears_nothing(hook: str, tmp_path: Path) -> None:
    configure(tmp_path)
    (tmp_path / ".claude" / ".roll-call-ignore").write_text("", encoding="utf-8")
    payloads = firing_payloads(tmp_path)
    result = run_hook(hook, payloads[hook], tmp_path)
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip(), f"{hook} spoke in a repository that opted out"
    assert not result.stderr.strip()


def test_the_same_payload_makes_a_configured_repository_speak(tmp_path: Path) -> None:
    """The silence above is about scope, not about the payloads being inert."""
    configure(tmp_path)
    payloads = firing_payloads(tmp_path)
    scan = run_hook("security_scan", payloads["security_scan"], tmp_path)
    assert json.loads(scan.stdout)["decision"] == "block"
    push = run_hook("publish_guard", payloads["publish_guard"], tmp_path)
    assert json.loads(push.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


# ------------------------------------------------------------ test command

def _build_command(project: Path, path_dir: Path | None) -> list[str] | None:
    env = {"CLAUDE_PROJECT_DIR": str(project), "PATH": str(path_dir) if path_dir else ""}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    code = (
        "import sys, json; sys.path.insert(0, sys.argv[1]); "
        "import backend_tests; print(json.dumps(backend_tests.build_command()))"
    )
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code, str(HOOKS)],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _engine_toml(project: Path, command: str) -> None:
    (project / ".claude").mkdir(exist_ok=True)
    (project / ".claude" / "engine.toml").write_text(
        f'[tests]\ncommand = {command}\ninterpreter = ""\n', encoding="utf-8"
    )


def test_a_python_module_command_runs_under_the_hooks_python(tmp_path: Path) -> None:
    _engine_toml(tmp_path, '["-m", "json.tool", "--help"]')
    command = _build_command(tmp_path, None)
    assert command is not None
    assert command[0] == sys.executable
    assert command[1:] == ["-m", "json.tool", "--help"]


def test_a_program_command_runs_that_program(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if os.name == "nt":
        runner = bin_dir / "suiterunner.bat"
        runner.write_text("@echo off\r\n", encoding="utf-8")
    else:
        runner = bin_dir / "suiterunner"
        runner.write_text("#!/bin/sh\n", encoding="utf-8")
        runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    _engine_toml(tmp_path, '["suiterunner", "test", "--silent"]')
    command = _build_command(tmp_path, bin_dir)
    assert command is not None
    assert Path(command[0]).name.startswith("suiterunner")
    assert command[0] != sys.executable
    assert command[1:] == ["test", "--silent"]


def test_a_program_that_is_not_installed_means_silence(tmp_path: Path) -> None:
    _engine_toml(tmp_path, '["suiterunner", "test"]')
    assert _build_command(tmp_path, None) is None


# --------------------------------------------------------- dependency audit

def test_a_node_manifest_is_never_sent_to_the_python_auditor(tmp_path: Path) -> None:
    configure(tmp_path)
    manifest = tmp_path / "package.json"
    manifest.write_text('{"name": "x", "dependencies": {"left-pad": "1.3.0"}}', encoding="utf-8")
    result = run_hook("dependency_audit", {"tool_input": {"file_path": str(manifest)}}, tmp_path)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "pip" not in out.lower(), out
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "UNCHECKED" in context, "an unavailable auditor must not read as clean"
    assert "npm" in context


def test_the_audit_can_be_switched_off(tmp_path: Path) -> None:
    configure(tmp_path)
    (tmp_path / ".claude" / "engine.toml").write_text(
        '[dependencies]\nenabled = false\n', encoding="utf-8"
    )
    manifest = tmp_path / "package.json"
    manifest.write_text('{"name": "x", "dependencies": {"left-pad": "1.3.0"}}', encoding="utf-8")
    result = run_hook("dependency_audit", {"tool_input": {"file_path": str(manifest)}}, tmp_path)
    assert result.returncode == 0
    assert not result.stdout.strip()


def test_requirements_txt_is_read_when_there_is_no_pyproject(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text(
        "# pinned\nrequests==2.31.0\n-r other.txt\n\nurllib3>=2  # transitive\n", encoding="utf-8"
    )
    code = (
        "import sys, json; sys.path.insert(0, sys.argv[1]); import dependency_audit as d; "
        "print(json.dumps(d.python_deps(sys.argv[2])))"
    )
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code, str(HOOKS), str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == ["requests==2.31.0", "urllib3>=2"]


# ------------------------------------------------------------- scaffold

def _scaffold(target: Path) -> dict:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCAFFOLD), "--project-name", "Acme", "--slug", "acme",
         "--target", str(target), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_init_keeps_the_session_ledgers_out_of_git(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    ignore = tmp_path / ".claude" / ".gitignore"
    assert ignore.is_file()
    lines = {ln.strip() for ln in ignore.read_text(encoding="utf-8").splitlines()}
    assert {".consults", ".agent-ran", ".route-stats"} <= lines


def test_an_existing_ledger_gitignore_is_left_alone(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    own = tmp_path / ".claude" / ".gitignore"
    own.write_text("mine\n", encoding="utf-8")
    report = _scaffold(tmp_path)
    assert own.read_text(encoding="utf-8") == "mine\n"
    assert str(own) in report["skipped"]


# ------------------------------------------------------ scan in test files

SECRET = 'password = "hunter22x"\n'  # project: allow py-secret-literal - fixture text the scan must flag


def test_a_fixture_secret_in_a_test_file_warns_instead_of_blocking(tmp_path: Path) -> None:
    configure(tmp_path)
    (tmp_path / "tests").mkdir()
    target = tmp_path / "tests" / "test_login.py"
    target.write_text(SECRET, encoding="utf-8")
    result = run_hook("security_scan", {"tool_input": {"file_path": str(target)}}, tmp_path)
    payload = json.loads(result.stdout)
    assert "decision" not in payload, "a test fixture must not block"
    assert "py-secret-literal" in payload["hookSpecificOutput"]["additionalContext"]


def test_the_same_secret_in_product_code_still_blocks(tmp_path: Path) -> None:
    configure(tmp_path)
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "login.py"
    target.write_text(SECRET, encoding="utf-8")
    result = run_hook("security_scan", {"tool_input": {"file_path": str(target)}}, tmp_path)
    assert json.loads(result.stdout)["decision"] == "block"


# ------------------------------------------------------- agent snapshot

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(project), *args], check=True,  # noqa: S603
                   capture_output=True, timeout=60)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    configure(tmp_path)
    (tmp_path / ".claude" / "engine.toml").write_text(
        '[project]\nname = "Acme"\nslug = "acme"\nsource_root = "src"\n', encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "-c", "user.email=t@example.com", "-c", "user.name=t", "add", "-A")
    _git(tmp_path, "-c", "user.email=t@example.com", "-c", "user.name=t",
         "commit", "-q", "-m", "base")
    return tmp_path


def _agent_round(repo: Path, data: Path, mutate) -> None:
    payload = {"tool_input": {"subagent_type": "security-engineer"}, "tool_use_id": "call-1"}
    before = run_hook("agent_snapshot", payload, repo, {"CLAUDE_PLUGIN_DATA": str(data)},
                      inherit_path=True)
    assert before.returncode == 0, before.stderr
    mutate()
    after = run_hook("agent_watch", payload, repo, {"CLAUDE_PLUGIN_DATA": str(data)},
                     inherit_path=True)
    assert after.returncode == 0, after.stderr


def _commit_prompt(repo: Path) -> dict | None:
    result = run_hook("unreviewed_agent_edits", {"tool_input": {"command": "git commit -m x"}},
                      repo, inherit_path=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else None


@needs_git
def test_the_commit_prompt_shows_only_what_the_agent_changed(repo: Path, tmp_path: Path) -> None:
    data = tmp_path / "plugin-data"
    data.mkdir()
    # The user's own edit, made before the agent ran.
    (repo / "src" / "a.py").write_text("A = 2\n", encoding="utf-8")

    def agent_edits() -> None:
        (repo / "src" / "b.py").write_text("B = 1\n", encoding="utf-8")

    _agent_round(repo, data, agent_edits)
    marker = (repo / ".claude" / ".agent-ran").read_text(encoding="utf-8")
    assert "\tsrc/b.py" in marker
    prompt = _commit_prompt(repo)
    assert prompt is not None
    reason = prompt["hookSpecificOutput"]["permissionDecisionReason"]
    assert "src/b.py" in reason
    assert "A = 2" not in reason, "the user's own edit is not the agent's"
    assert not list((data / "agent-pre").glob("*")), "the snapshot is consumed"


@needs_git
def test_an_agent_that_changed_nothing_does_not_interrupt_the_commit(
    repo: Path, tmp_path: Path
) -> None:
    data = tmp_path / "plugin-data"
    data.mkdir()
    (repo / "src" / "a.py").write_text("A = 2\n", encoding="utf-8")
    _agent_round(repo, data, lambda: None)
    marker = (repo / ".claude" / ".agent-ran").read_text(encoding="utf-8")
    assert marker.rstrip().endswith("\t-")
    assert _commit_prompt(repo) is None
    assert not (repo / ".claude" / ".agent-ran").exists(), "the marker is consumed either way"


@needs_git
def test_without_a_snapshot_the_whole_source_diff_is_shown(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("A = 2\n", encoding="utf-8")
    payload = {"tool_input": {"subagent_type": "security-engineer"}}
    run_hook("agent_watch", payload, repo, inherit_path=True)
    marker = (repo / ".claude" / ".agent-ran").read_text(encoding="utf-8")
    assert "\t" not in marker
    prompt = _commit_prompt(repo)
    assert prompt is not None
    assert "A = 2" in prompt["hookSpecificOutput"]["permissionDecisionReason"]


def test_the_snapshot_hook_is_wired_before_agents() -> None:
    wiring = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    pre = [
        (group.get("matcher"), handler["command"])
        for group in wiring["hooks"]["PreToolUse"]
        for handler in group["hooks"]
    ]
    assert any(m == "Agent" and c.endswith("agent_snapshot") for m, c in pre)
