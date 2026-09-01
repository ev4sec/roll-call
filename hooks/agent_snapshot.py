#!/usr/bin/env python
"""PreToolUse hook: note the state of the source tree before an agent runs.

Pairs with `agent_watch.py`, which fires after the agent finishes. Between the
two, the engine learns exactly which files under the source root the agent
changed, so the post-agent commit prompt can show those files and nothing
else. Without this snapshot the prompt shows the whole source diff, which is
still correct, only broader.

The snapshot lives under the harness-provided plugin data directory, keyed by
the tool call id, and is consumed and removed by `agent_watch.py`. A
background agent gets no snapshot: it reports back before it has done
anything, so a comparison at that moment would say it changed nothing.

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

    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict) and tool_input.get("run_in_background"):
        return 0

    project = _engine.project_dir()
    target = _engine.snapshot_file(project, payload.get("tool_use_id"))
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
