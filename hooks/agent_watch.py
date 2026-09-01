#!/usr/bin/env python
"""PostToolUse hook: remember that an advisory agent ran.

Two files, two jobs, and they must not be merged:

  `.claude/.agent-ran`
      A marker saying an agent has touched the tree since the last commit.
      Cleared by the commit guard. Each line names the agent and, when the
      pre-run snapshot from `agent_snapshot.py` is available, the source
      files that changed while it ran.

  `.claude/.consults`
      An append-only `<agent>\\t<unix-ts>` ledger, read by `consult_router.py`
      to decide whether the seat that owns a change was actually asked.
      Never cleared.

**Why the marker exists.** Review agents that have Bash mutate source to check
whether a guard fires. That is legitimate technique and it is how they earn
their findings, but they do not reliably restore what they changed. On the
project this engine came from it happened twice in one session, and the second
one reached a commit: a length prefix removed from an integrity preimage,
landing in the very commit that documented the hazard, because `git add -A`
plus a glance at the *file list* is not reading the diff.

The written control was "read the diff after an agent runs". This is that
control, mechanized, because an instruction that was broken the same day it was
written is not a control.

**Why the ledger is written here rather than by the session.** A ledger on the
honor system fails exactly the way a prose routing table fails: it is read at
session start and forgotten by the third edit. The hook fires whether or not
anyone remembered.

**Marker line format.** `HH:MM:SS <agent>` on its own means the changed files
are unknown and the commit guard shows the whole source diff. A tab followed
by a comma-separated file list names what changed; a tab followed by `-` means
the comparison ran and nothing under the source root changed.

Produces no output and never blocks.
"""

import json
import sys
import time

import _engine

MARKER = ".claude/.agent-ran"
CONSULTS = ".claude/.consults"


def changed_files(project, payload) -> list[str] | None:
    """Files under the source root the agent changed, or None if unknown."""
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict) and tool_input.get("run_in_background"):
        return None
    before_path = _engine.snapshot_file(project, payload.get("tool_use_id"))
    if before_path is None or not before_path.is_file():
        return None
    try:
        before = json.loads(before_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        before = None
    try:
        before_path.unlink()
    except OSError:
        pass
    if not isinstance(before, dict):
        return None
    after = _engine.source_snapshot(project, str(_engine.get("project", "source_root")))
    if after is None:
        return None
    return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if not _engine.initialized():
        return 0

    project = _engine.project_dir()
    marker = project / MARKER

    tool_input = payload.get("tool_input") or {}
    name = str(tool_input.get("subagent_type", "agent")) if isinstance(tool_input, dict) else "agent"
    changed = changed_files(project, payload)
    line = f"{time.strftime('%H:%M:%S')} {name}"
    if changed is not None:
        line += "\t" + (",".join(f.replace(",", "%2C") for f in changed) or "-")

    # Append rather than overwrite: several agents may run before one commit,
    # and the commit guard should name all of them.
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        with marker.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        # A hook that cannot write its marker must not break the session. The
        # cost is one unguarded commit, which is where we were before.
        pass

    try:
        with (project / CONSULTS).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}\t{time.time():.0f}\n")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
