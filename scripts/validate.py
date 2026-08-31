#!/usr/bin/env python
"""End-to-end validation: stand up real repositories and drive the real hooks.

**Why this exists separately from the test suite.** `tests/` checks the parts.
This checks that installing the thing and using it produces the behavior the
README promises, by building actual repositories on disk and invoking each hook
exactly the way `hooks.json` says the harness will: through `run.sh`, with the
event JSON on stdin and `CLAUDE_PROJECT_DIR` in the environment.

The one step it cannot perform is `/plugin install`, which is a Claude Code
action rather than a filesystem one. Everything downstream of that is real.

Run: python scripts/validate.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((PASS if ok else FAIL, name, detail))
    return ok


def fire(hook: str, payload: dict, project: Path, extra_env: dict | None = None):
    """Invoke a hook the way hooks.json does: through run.sh."""
    import os

    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env.update(extra_env or {})
    return subprocess.run(  # noqa: S603
        ["sh", str(ROOT / "hooks" / "run.sh"), hook],
        input=json.dumps(payload), capture_output=True, text=True,
        timeout=120, env=env, cwd=str(project),
    )


def scaffold(project: Path, **kw) -> subprocess.CompletedProcess:
    args = ["--project-name", kw.get("name", "Scratch"),
            "--slug", kw.get("slug", "scratch"),
            "--source-root", kw.get("source_root", "src"),
            "--test-dir", kw.get("test_dir", "tests"),
            "--target", str(project), "--json"]
    return subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "scaffold.py"), *args],
        capture_output=True, text=True, timeout=120,
    )


def git(project: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(project), *args],  # noqa: S603
                          capture_output=True, text=True, timeout=60)


# ---------------------------------------------------------------- scenarios --

def scenario_python_repo(tmp: Path) -> None:
    project = tmp / "python-repo"
    (project / "src" / "scratch").mkdir(parents=True)
    (project / "src" / "scratch" / "models.py").write_text("class A:\n    pass\n",
                                                           encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[project]\nname = "scratch"\nversion = "0.1.0"\n', encoding="utf-8")
    out = scaffold(project, source_root="src/scratch")
    check("python repo: scaffold succeeds", out.returncode == 0, out.stderr[:200])
    report = json.loads(out.stdout)
    check("python repo: 29 files written", len(report["written"]) == 29,
          f"got {len(report['written'])}")
    check("python repo: notes lifted", report["notes_lifted"] > 20)
    check("python repo: judgment slots preserved", report["judgment_slots"] > 50)

    # The board and the brief must be free of installer guidance.
    brief = (project / ".claude" / "agent-brief.md").read_text(encoding="utf-8")
    check("python repo: brief has no installer comments",
          "INSTANTIATION" not in brief)


def scenario_node_repo(tmp: Path) -> None:
    """A Node project must not be told to run pytest or build a wheel."""
    project = tmp / "node-repo"
    (project / "src").mkdir(parents=True)
    (project / "package.json").write_text('{"name":"scratch"}', encoding="utf-8")
    out = scaffold(project)
    check("node repo: scaffold succeeds", out.returncode == 0, out.stderr[:200])

    conf = project / ".claude" / "engine.toml"
    conf.write_text(
        '[project]\nname = "Scratch"\nslug = "scratch"\nsource_root = "src"\n'
        '[tests]\ndir = "tests"\ncommand = ["test", "--silent"]\n'
        'interpreter = "npm"\nroot_marker = "package.json"\n'
        '[artifact]\nenabled = false\n', encoding="utf-8")
    proc = fire("artifact_check", {
        "tool_name": "Write",
        "tool_input": {"file_path": str(project / "package.json")},
    }, project)
    check("node repo: artifact check stays silent when disabled",
          proc.returncode == 0 and not proc.stdout.strip(),
          f"rc={proc.returncode} out={proc.stdout[:120]}")


def scenario_existing_files(tmp: Path) -> None:
    project = tmp / "existing"
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / "CLAUDE.md").write_text("# Mine\n\nMy rules.\n", encoding="utf-8")
    (project / ".claude" / "agents" / "systems-architect.md").write_text(
        "my own seat\n", encoding="utf-8")
    out = scaffold(project)
    report = json.loads(out.stdout)
    text = (project / "CLAUDE.md").read_text(encoding="utf-8")
    check("collision: user CLAUDE.md survives verbatim", text.startswith("# Mine"))
    check("collision: engine still reachable",
          "@.claude/operating-procedure.md" in text)
    check("collision: user agent untouched",
          (project / ".claude" / "agents" / "systems-architect.md")
          .read_text(encoding="utf-8") == "my own seat\n")
    check("collision: skip is reported",
          any("systems-architect" in s for s in report["skipped"]))
    check("collision: other seats still arrive",
          (project / ".claude" / "agents" / "test-strategist.md").is_file())


def scenario_onboarding(tmp: Path) -> None:
    project = tmp / "onboarding"
    project.mkdir()
    data = tmp / "plugin-data"
    env = {"CLAUDE_PLUGIN_DATA": str(data)}

    first = fire("session_start", {"hook_event_name": "SessionStart"}, project, env)
    check("onboarding: fresh repo is offered init",
          "/roll-call:init" in first.stdout, first.stdout[:120])
    second = fire("session_start", {"hook_event_name": "SessionStart"}, project, env)
    check("onboarding: second session is silent", not second.stdout.strip(),
          second.stdout[:120])

    scaffold(project)
    third = fire("session_start", {"hook_event_name": "SessionStart"}, project, env)
    check("onboarding: configured repo is silent", not third.stdout.strip(),
          third.stdout[:120])


def scenario_the_consult_block(tmp: Path) -> None:
    """The product. If only one check runs, it is this one."""
    project = tmp / "routed"
    (project / "src").mkdir(parents=True)
    target = project / "src" / "models.py"
    target.write_text("class Order:\n    pass\n", encoding="utf-8")
    scaffold(project)

    (project / ".claude" / "routing.toml").write_text(
        '[settings]\nfresh_hours = 24\nmax_parallel = 4\n\n'
        '[[rule]]\nid = "data-model"\npaths = ["src/models.py"]\n'
        'agents = ["systems-architect"]\nlevel = "required"\n'
        'question = "Name the column, its type, and what it costs to change."\n'
        'why = "A shipped column is a migration."\n', encoding="utf-8")

    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}

    blocked = fire("consult_router", payload, project)
    check("consult: an owed required consult blocks", blocked.returncode == 2,
          f"rc={blocked.returncode}")
    check("consult: it names the owning seat",
          "systems-architect" in blocked.stderr, blocked.stderr[:160])
    check("consult: it carries the actual question",
          "what it costs to change" in blocked.stderr, blocked.stderr[:160])

    # Now record a consult the way agent_watch does, and confirm it clears.
    fire("agent_watch", {"tool_name": "Agent",
                         "tool_input": {"subagent_type": "systems-architect"}},
         project)
    ledger = project / ".claude" / ".consults"
    check("consult: the ledger is written by the hook", ledger.is_file())
    check("consult: the ledger names the seat",
          "systems-architect" in ledger.read_text(encoding="utf-8"))

    cleared = fire("consult_router", payload, project)
    check("consult: a fresh consult clears the block", cleared.returncode == 0,
          f"rc={cleared.returncode} err={cleared.stderr[:160]}")

    # An unrelated file must never summon anyone.
    other = project / "src" / "unrelated.py"
    other.write_text("x = 1\n", encoding="utf-8")
    quiet = fire("consult_router",
                 {"tool_name": "Edit", "tool_input": {"file_path": str(other)}},
                 project)
    check("consult: an unrelated file summons nobody",
          quiet.returncode == 0 and not quiet.stderr.strip(),
          quiet.stderr[:160])


def scenario_advisory_posture(tmp: Path) -> None:
    project = tmp / "advisory"
    (project / "src").mkdir(parents=True)
    target = project / "src" / "models.py"
    target.write_text("x = 1\n", encoding="utf-8")
    scaffold(project)
    rule = ('[settings]\nfresh_hours = 24\nmax_parallel = 4\n\n'
            '[[rule]]\nid = "m"\npaths = ["src/models.py"]\n'
            'agents = ["systems-architect"]\nlevel = "{}"\n'
            'question = "q"\nwhy = "w"\n')
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}

    (project / ".claude" / "routing.toml").write_text(rule.format("advised"),
                                                      encoding="utf-8")
    advised = fire("consult_router", payload, project)
    check("posture: advised never blocks", advised.returncode == 0,
          f"rc={advised.returncode}")
    check("posture: advised still mentions the seat",
          "systems-architect" in advised.stderr, advised.stderr[:120])

    (project / ".claude" / "routing.toml").write_text(rule.format("required"),
                                                      encoding="utf-8")
    required = fire("consult_router", payload, project)
    check("posture: promoting to required blocks", required.returncode == 2)


def scenario_publish_guard(tmp: Path) -> None:
    project = tmp / "publishing"
    project.mkdir()
    scaffold(project)
    git(project, "init", "-q")

    bare = tmp / "mirror.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)],  # noqa: S603
                   capture_output=True, timeout=60)
    git(project, "remote", "add", "origin", str(bare))
    local = fire("publish_guard",
                 {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}},
                 project)
    check("publish: a push to a local mirror stays silent",
          local.returncode == 0 and "ask" not in local.stdout,
          local.stdout[:160])

    git(project, "remote", "set-url", "origin",
        "https://github.com/someone/something.git")
    remote = fire("publish_guard",
                  {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}},
                  project)
    check("publish: a push to a gated host asks", "ask" in remote.stdout,
          remote.stdout[:200])

    upload = fire("publish_guard",
                  {"tool_name": "Bash", "tool_input": {"command": "npm publish"}},
                  project)
    check("publish: a registry upload asks regardless of remote",
          "ask" in upload.stdout, upload.stdout[:200])

    benign = fire("publish_guard",
                  {"tool_name": "Bash", "tool_input": {"command": "git stash push -u"}},
                  project)
    check("publish: `git stash push` is not a publish",
          "ask" not in benign.stdout, benign.stdout[:160])


def scenario_plugin_update(tmp: Path) -> None:
    """A plugin update must not reach into a repository and rewrite it."""
    project = tmp / "updated"
    project.mkdir()
    scaffold(project)
    seat = project / ".claude" / "agents" / "systems-architect.md"
    tuned = seat.read_text(encoding="utf-8") + "\n## Local knowledge\nOur ORM is X.\n"
    seat.write_text(tuned, encoding="utf-8")
    routing = project / ".claude" / "routing.toml"
    routing.write_text("[settings]\nfresh_hours = 48\nmax_parallel = 2\n",
                       encoding="utf-8")

    scaffold(project)  # stands in for a re-run after an update

    check("update: a tuned seat is not overwritten",
          seat.read_text(encoding="utf-8") == tuned)
    check("update: an edited routing table is not overwritten",
          "fresh_hours = 48" in routing.read_text(encoding="utf-8"))


def scenario_project_suite(tmp: Path) -> None:
    """The suite init installs must run, and must fail in exactly one place."""
    project = tmp / "suite"
    (project / "src").mkdir(parents=True)
    scaffold(project)
    import os

    env = dict(os.environ)
    # Point the project-side suite at the hooks it would find in a real install,
    # so the router assertions actually run instead of skipping.
    env["ROLL_CALL_HOOKS"] = str(ROOT / "hooks")
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-q", "tests", "--no-header", "-p",
         "no:cacheprovider"],
        cwd=str(project), capture_output=True, text=True, timeout=300, env=env,
    )
    out = proc.stdout + proc.stderr
    check("project suite: it collects and runs", "error during collection" not in out,
          out[-400:])
    check("project suite: the router assertions actually ran",
          "skipped" not in out.split("passed")[-1][:40] or "passed" in out,
          out[-200:])
    check("project suite: the refusals guard fails on purpose",
          "test_the_refusal_list_has_been_filled_in" in out, out[-400:])
    check("project suite: nothing else fails",
          out.count("FAILED") == 1, out[-500:])


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for fn in (scenario_python_repo, scenario_node_repo,
                   scenario_existing_files, scenario_onboarding,
                   scenario_the_consult_block, scenario_advisory_posture,
                   scenario_publish_guard, scenario_plugin_update,
                   scenario_project_suite):
            try:
                fn(tmp)
            except Exception as exc:  # noqa: BLE001
                check(f"{fn.__name__} (crashed)", False, repr(exc)[:200])

    width = max(len(n) for _, n, _ in results)
    failed = 0
    for status, name, detail in results:
        print(f"  [{status}] {name.ljust(width)}  {detail if status == FAIL else ''}")
        failed += status == FAIL
    print(f"\n  {len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
