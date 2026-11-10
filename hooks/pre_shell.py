#!/usr/bin/env python
"""PreToolUse hook: both shell guards in one process.

Every shell command used to start two hooks, the publish guard and the
post-agent commit guard, each paying for its own shell and its own
interpreter to conclude, almost always, that the command was neither a
publish nor a commit. This file runs both and answers once.

**The only thing it ever returns is a confirmation prompt.** Each guard hands
back the text of its prompt or nothing. One reason is shown as it is; two are
shown together, the publish reason first. No command is approved and none is
refused here: the person at the keyboard decides.

**Each guard keeps its own failure direction.** The publish guard fails
closed, so if it cannot run at all the answer is a prompt, never silence. The
commit guard fails open, so a fault in it costs one unguarded commit and
never blocks the publish check sitting beside it.

Both guards still run on their own, as `publish_guard.py` and
`unreviewed_agent_edits.py`; this file adds no logic to either.
"""

from __future__ import annotations

import json
import sys

import _engine
import publish_guard
import unreviewed_agent_edits


def reasons(raw: object) -> list[str]:
    """Every prompt this command earns, publish first."""
    found: list[str] = []

    try:
        publish = publish_guard.reason_for(raw)
    except Exception:
        # Fail closed, the same direction the guard itself takes.
        publish = None
        if _engine.initialized():
            publish = (
                f"{_engine.name()} policy: the publish check could not run on "
                f"this command. Confirm this is safe to run."
            )
    if publish:
        found.append(publish)

    try:
        payload = json.loads(raw)  # type: ignore[arg-type]
    except Exception:
        payload = None
    if isinstance(payload, dict):
        try:
            commit = unreviewed_agent_edits.reason_for(payload)
        except Exception:
            commit = None
        if commit:
            found.append(commit)
    return found


def main() -> int:
    try:
        raw: object = sys.stdin.read()
    except Exception:
        raw = None

    found = reasons(raw)
    if not found:
        return 0
    return publish_guard.ask("\n\n".join(found))


if __name__ == "__main__":
    sys.exit(main())
