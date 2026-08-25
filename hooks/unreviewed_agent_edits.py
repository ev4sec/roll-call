#!/usr/bin/env python
"""PreToolUse hook: put the source diff in front of you before a post-agent commit.

Fires only when **both** are true: an advisory agent ran since the last commit,
and the configured source root differs from HEAD. Then it returns
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
not follow an agent, so the window is small and the prompt stays meaningful. It
also reads only the source root: a scratch test file an agent left behind is a
finding to read, not a hazard to block on, and the tests are run by another
hook anyway.

The marker is cleared when this fires: one prompt per agent run, not per
commit. If it never fires, nothing was at risk.

Configure the source root in `.claude/engine.toml` under `[project]`.
"""

import json
import os
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


def source_diff(project: Path, source_root: str) -> str:
    """Working-tree and staged changes under the source root, against HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", source_root],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = str(payload.get("tool_input", {}).get("command", ""))
    if not command or not is_git_commit(command):
        return 0

    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    marker = project / MARKER
    if not marker.exists():
        return 0

    diff = source_diff(project, str(_engine.get("project", "source_root")))
    try:
        agents = marker.read_text(encoding="utf-8").strip().splitlines()
        marker.unlink()
    except OSError:
        agents = []

    if not diff.strip():
        # An agent ran but touched no source. Nothing to look at.
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
