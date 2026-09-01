#!/usr/bin/env python
"""PreToolUse hook: put the source diff in front of you before a post-agent commit.

Fires only when **both** are true: an advisory agent ran since the last commit,
and the source it touched differs from HEAD. Then it returns
permissionDecision "ask" with the actual diff in the prompt, so the decision is
made while looking at the change rather than at a list of filenames.

**The failure it exists for.** A review agent removed a length prefix from an
integrity preimage: reducing a tamper-evidence hash input to plain
concatenation, where component tuples collide, and did not restore it. It went
in on `git add -A` and a glance at the file list, in the commit that documented
the hazard. No test caught it, because it was precisely the mutation no test
covered. It surfaced hours later when a pinned-vector test failed.

**Why it is scoped this narrowly.** Firing on every commit would be ignored
within a day. An alarm that cries wolf is worse than no alarm. Most commits do
not follow an agent, so the window is small and the prompt stays meaningful.
When `agent_snapshot.py` and `agent_watch.py` recorded which files each agent
changed, the prompt carries only those files, and a commit after an agent that
changed nothing under the source root is not interrupted at all. When that
record is unavailable, the prompt falls back to the whole source-root diff.
It reads only the source root either way: a scratch test file an agent left
behind is a finding to read, not a hazard to block on, and the tests are run
by another hook anyway.

The marker is cleared when this fires: one prompt per agent run, not per
commit. If it never fires, nothing was at risk.

Configure the source root in `.claude/engine.toml` under `[project]`.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import _engine

MARKER = ".claude/.agent-ran"
MAX_DIFF_LINES = 120

SEGMENT_SPLIT = re.compile(r"(?:\|\||&&|[;|&\n\r])")
GIT_WORD = re.compile(r"(?<![\w./-])git(?:\.exe)?(?![\w.-])", re.IGNORECASE)
COMMIT_WORD = re.compile(r"(?<![\w-])commit(?![\w-])", re.IGNORECASE)


def is_git_commit(command: str) -> bool:
    """True if any segment of the command line is a `git commit`."""
    return any(
        GIT_WORD.search(segment) and COMMIT_WORD.search(segment)
        for segment in SEGMENT_SPLIT.split(command)
    )


def read_marker(text: str) -> tuple[list[str], list[str] | None]:
    """(agent labels, files the agents changed) from the marker.

    The file list is None when any agent's changes are unknown, which sends
    the caller to the whole source-root diff.
    """
    agents: list[str] = []
    files: set[str] = set()
    known = True
    for line in text.strip().splitlines():
        head, tab, tail = line.partition("\t")
        agents.append(head)
        if not tab:
            known = False
        elif tail != "-":
            files.update(f.replace("%2C", ",") for f in tail.split(",") if f)
    return agents, (sorted(files) if known else None)


def _git(project: Path, args: list[str], ok=(0,)) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode in ok else ""


def source_diff(project: Path, paths: list[str]) -> str:
    """Working-tree and staged changes against HEAD, for the given paths."""
    if not paths:
        return ""
    diff = _git(project, ["diff", "HEAD", "--", *paths])
    untracked = _git(project, ["ls-files", "--others", "--exclude-standard", "--", *paths])
    for rel in untracked.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        try:
            body = (project / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            body = ""
        diff += f"new file (untracked): {rel}\n"
        diff += "".join(f"+{line}\n" for line in body.splitlines())
    return diff


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if not _engine.initialized():
        return 0

    command = str((payload.get("tool_input") or {}).get("command", ""))
    if not command or not is_git_commit(command):
        return 0

    project = _engine.project_dir()
    marker = project / MARKER
    if not marker.exists():
        return 0

    try:
        agents, files = read_marker(marker.read_text(encoding="utf-8"))
        marker.unlink()
    except OSError:
        agents, files = [], None

    if files is None:
        files = [str(_engine.get("project", "source_root"))]
    diff = source_diff(project, files)

    if not diff.strip():
        # The agents touched nothing under the source root. Nothing to look at.
        return 0

    lines = diff.splitlines()
    excerpt = "\n".join(lines[:MAX_DIFF_LINES])
    if len(lines) > MAX_DIFF_LINES:
        excerpt += f"\n... {len(lines) - MAX_DIFF_LINES} more lines"

    who = ", ".join(agents) if agents else "an agent"
    reason = (
        f"An advisory agent ran since the last commit ({who}), and the source "
        f"root has changed. Agents mutate source to test whether guards fire "
        f"and do not reliably restore it. One such edit reached a commit on "
        f"the project this engine came from, in the commit documenting that "
        f"hazard.\n\n"
        f"Read this as content, not as filenames. If any hunk is not yours, "
        f"`git checkout --` that file and re-run the suite before committing.\n\n"
        f"{excerpt}"
    )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
