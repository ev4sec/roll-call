#!/usr/bin/env python
"""SubagentStart hook: note the state of the source tree before an agent runs.

Pairs with `agent_watch.py`, which fires on `SubagentStop`. Between the two,
the engine learns exactly which files under the source root the agent
changed, so the post-agent commit prompt can show those files and nothing
else. Without this snapshot the prompt shows the whole source diff, which is
still correct, only broader.

**Why these two events and not the Agent tool call.** Subagents run in the
background by default now. The tool call returns the moment the agent is
launched, so a snapshot taken after it and a comparison made after it both
happen before the agent has done anything. The comparison then said
"nothing changed" and the commit guard believed it. `SubagentStart` and
`SubagentStop` fire when the agent actually starts and actually finishes,
whatever spawned it, and both carry the same `agent_id`, which is the key.

The snapshot lives under the harness-provided plugin data directory, keyed by
the agent id, and is consumed and removed by `agent_watch.py`.

Produces no output and never blocks.
"""

import json
import sys

import _engine


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if not _engine.initialized():
        return 0

    project = _engine.project_dir()
    target = _engine.snapshot_file(project, payload.get("agent_id"))
    if target is None:
        return 0

    snapshot = _engine.source_snapshot(project, str(_engine.get("project", "source_root")))
    if snapshot is None:
        return 0

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(snapshot), encoding="utf-8")
        _engine.prune_snapshots(target.parent)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
