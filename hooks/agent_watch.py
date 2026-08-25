#!/usr/bin/env python
"""PostToolUse hook: remember that an advisory agent ran.

Two files, two jobs, and they must not be merged:

  `.claude/.agent-ran`
      A marker saying an agent has touched the tree since the last commit.
      Cleared by the commit guard.

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

Produces no output and never blocks.
"""

import json
import os
import sys
import time
from pathlib import Path

MARKER = ".claude/.agent-ran"
CONSULTS = ".claude/.consults"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    marker = project / MARKER

    # Append rather than overwrite: several agents may run before one commit,
    # and the commit guard should name all of them.
    name = str(payload.get("tool_input", {}).get("subagent_type", "agent"))
    line = f"{time.strftime('%H:%M:%S')} {name}\n"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        with marker.open("a", encoding="utf-8") as handle:
            handle.write(line)
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
