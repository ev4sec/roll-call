#!/usr/bin/env python
"""SubagentStop hook: record the consult and queue the seat's claims.

One process for the two things that happen when an agent finishes:
`agent_watch.py` writes the unreviewed-edits marker and stamps the consult
ledger, and `agent_report.py` queues every labeled claim for a verdict. They
used to be two hooks with two interpreter starts.

The ledger stamp comes first and is never skipped: the router's freshness
check reads it, and a consult that happened but was not recorded would be
demanded again. A fault in either half leaves the other to finish.

Produces no output and never blocks.
"""

from __future__ import annotations

import json
import sys

import agent_report
import agent_watch


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    for step in (agent_watch.run, agent_report.run):
        try:
            step(payload)
        except Exception:
            # Silent by contract: the harness hands this hook's output to the
            # subagent, and a crash here must not cost the other record.
            continue
    return 0


if __name__ == "__main__":
    sys.exit(main())
