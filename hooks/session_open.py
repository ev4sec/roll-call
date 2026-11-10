#!/usr/bin/env python
"""SessionStart hook: the setup notice and the ledger rebrief in one process.

Two things can be worth saying when a session's context begins, and they go
to different readers:

  the setup notice   for the person, from `session_start.py`: roll-call is
                     installed but not set up here, or set up and damaged.
                     Only on a plain startup, as before; a resume or a
                     compaction is not the moment to offer init.
  the rebrief        for the session, from `session_rebrief.py`: what the
                     ledgers hold that a rebuilt context no longer remembers.
                     On every kind of start.

**The output keeps the shape each half always had.** The rebrief alone is
plain text on stdout, which the harness adds to the session's context. The
notice alone is a `systemMessage`. Only when both speak at once, which takes
a damaged setup with live ledgers, do they share one JSON object.

Never blocks, always exits 0.
"""

from __future__ import annotations

import json
import sys

import session_rebrief
import session_start


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    source = payload.get("source")
    message = None
    if not source or source == "startup":
        try:
            message = session_start.notice()
        except Exception:
            message = None

    try:
        context = session_rebrief.text_for(payload)
    except Exception:
        context = ""

    if message and context:
        json.dump(
            {
                "systemMessage": message,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                },
            },
            sys.stdout,
        )
    elif message:
        json.dump({"systemMessage": message}, sys.stdout)
    elif context:
        sys.stdout.write(context)
    return 0


if __name__ == "__main__":
    sys.exit(main())
