#!/usr/bin/env python
"""Stop hook: say, at the end of a turn, which required consults are still owed.

**Why this exists.** The router blocks at edit time, and the block names the
seat and the question. Then the session does other work, the turn ends, and
the owed consult is a line some distance up the transcript. Nothing said, at
the moment the turn closed, that the router's demand was still unmet. This
hook does. It reuses the rebrief hook's reader, so it cannot disagree with
the router about which rules fired this session or which seats are fresh.

**What it does not do.** It never blocks the stop. A `Stop` hook can force
the model to keep going, and a forced continuation over a consult the session
has decided to skip is the over-consulting failure the procedure warns about.
The router already refuses the edit; this is the reminder, delivered as
context for the next turn, and it is silent when nothing is owed.

Output is the harness's JSON shape for this event, on stdout. Exit 0 always.
"""

from __future__ import annotations

import json
import sys

import _engine
import session_rebrief


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if not _engine.have_project_dir() or not _engine.initialized():
        return 0

    project = _engine.project_dir()
    owed, _ = session_rebrief.owed_lines(project, payload.get("session_id"))
    if not owed:
        return 0

    text = (
        "roll-call: the turn ended with consults the router demanded still not "
        "on the ledger (full text in .claude/routing.toml):\n" + "\n".join(owed)
        + "\nSpawn the seat, or say in the message why the consult is being skipped."
    )
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": text}},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
