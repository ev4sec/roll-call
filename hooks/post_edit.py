#!/usr/bin/env python
"""PostToolUse hook: the consult router and the pattern scan in one process.

Every edit used to start two hooks, each with its own shell and interpreter.
This file runs both and reports for both.

**The router's exit code is still the guarantee.** A required consult with
nothing fresh on the ledger exits 2 with the router's message on stderr,
exactly as `consult_router.py` does alone. When the scan also has something
to say about the same edit, its text is added to that message, because an
exit of 2 is read from stderr and anything printed beside it would be lost.

**When the router has no demand, the scan answers as it always has**: its
JSON on stdout, a block for a blocking finding and context for a warning.

**Neither check can take the other down.** They were separate processes, so
a fault in one never silenced the other. That stays true: each runs behind
its own guard, and a check that fails says so on stderr and gets out of the
way.

Bandit is not run here. It costs several times what the rest of an edit
costs, so `post_batch.py` runs it once over the files a batch wrote.
"""

from __future__ import annotations

import json
import sys

import consult_router
import security_scan


def scan_text_of(result: dict) -> str:
    """The scan's findings as plain text, for riding along on stderr."""
    if result.get("decision") == "block" and result.get("reason"):
        return str(result["reason"])
    extra = result.get("hookSpecificOutput") or {}
    if isinstance(extra, dict) and extra.get("additionalContext"):
        return str(extra["additionalContext"])
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    try:
        code = consult_router.run(payload)
    except Exception as exc:
        # Fails open, as the router does on its own.
        print(f"consult_router: could not run ({exc})", file=sys.stderr)
        code = 0

    try:
        result = security_scan.check(payload)
    except Exception as exc:
        print(f"security_scan: could not run ({exc})", file=sys.stderr)
        result = None

    if code == 2:
        if result:
            text = scan_text_of(result)
            if text:
                print("\n" + text, file=sys.stderr)
        return 2

    if result:
        print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
