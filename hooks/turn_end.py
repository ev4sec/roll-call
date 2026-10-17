#!/usr/bin/env python
"""Stop hook: say, at the end of a turn, which required consults are still owed.

**Why this exists.** The router blocks at edit time, and the block names the
seat and the question. Then the session does other work, the turn ends, and
the owed consult is a line some distance up the transcript. Nothing said, at
the moment the turn closed, that the router's demand was still unmet. This
hook does. It reuses the rebrief hook's reader, so it cannot disagree with
the router about which rules fired this session or which seats are fresh.

**It also looks at the tree, not only at the router's memory.** The router
sees writes made through the editor tools. A file changed by a shell command,
a script, or a git operation never reaches it, and that gap was documented
rather than closed. Here it mostly closes: the working tree's changes against
HEAD, plus untracked files, are matched against the same rules with the same
freshness rule. A required rule the router never saw this session, matching a
file that changed by some other means, with no fresh consult, is named once
per session. Two git calls per turn is the whole cost.

**It says each thing once per session.** Context returned from a `Stop` hook
is delivered as feedback, and the session answers feedback, so a reminder
repeated at every turn end becomes a forced continuation: the first version of
this hook made a session restate the same declared skip seven times in one
turn. A forced continuation over a consult the session has decided to skip is
the over-consulting failure the procedure warns about. So each owed rule is
named at one turn end per session and then left to the router, which still
refuses every further edit, and to the rebrief, which still restates the debt
when the context is rebuilt. It never returns a block.

Output is the harness's JSON shape for this event, on stdout. Exit 0 always.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _engine
import consult_router
import session_rebrief

#: Session-state prefixes for what this hook has already said this session:
#: router-owed rules it has reminded about, and tree changes it has named. The
#: rebrief reader skips both, so neither masquerades as a rule the router fired.
STOP_PREFIX = "stop:"
TREE_PREFIX = "tree:"


def router_owed(project: Path, session_id: object) -> list[str]:
    """The router's unmet demands this session, each named at one turn end."""
    owed, _ = session_rebrief.owed_rules(project, session_id)
    if not owed:
        return []
    state = consult_router._state_file(project, session_id)
    seen = consult_router._seen_rules(state)
    fresh = [(key, line) for key, line in owed if STOP_PREFIX + key not in seen]
    if fresh:
        consult_router._record_rules(state, [STOP_PREFIX + key for key, _ in fresh])
    return [line for _, line in fresh]


def changed_paths(project: Path) -> list[str] | None:
    """Repo-relative paths changed against HEAD by any means, or None without git."""
    diff = _engine._git_stdout(project, ["diff", "--name-only", "--relative", "HEAD"])
    if diff is None:
        return None
    untracked = _engine._git_stdout(project, ["ls-files", "--others", "--exclude-standard"])
    changed: list[str] = []
    for text in (diff, untracked or ""):
        for line in text.splitlines():
            rel = line.strip().replace("\\", "/")
            if rel and rel not in changed:
                changed.append(rel)
    return changed


def tree_owed(project: Path, session_id: object) -> list[str]:
    """Required consults owed for files the router never saw, named once each."""
    if consult_router.tomllib is None:
        return []
    try:
        settings, rules = consult_router._load_rules(project)
    except (OSError, consult_router.tomllib.TOMLDecodeError):
        return []
    changed = changed_paths(project)
    if not changed:
        return []

    state = consult_router._state_file(project, session_id)
    seen = consult_router._seen_rules(state)
    lines: list[str] = []
    record: list[str] = []
    for rel in sorted(changed):
        required, _ = consult_router.owed(rel, project, settings, rules)
        for rule in required:
            key = consult_router._rule_key(rule)
            # The router already demanded this rule this session, or the tree
            # check already named it: either way it has been said.
            if key in seen or TREE_PREFIX + key in seen:
                continue
            seen.add(TREE_PREFIX + key)
            record.append(TREE_PREFIX + key)
            missing = ", ".join(str(a) for a in rule["missing"])  # type: ignore[union-attr]
            lines.append(f"  [{rule.get('id', '?')}] -> {missing} ({rel})")
    if record:
        consult_router._record_rules(state, record)
    return lines


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if not _engine.have_project_dir() or not _engine.initialized():
        return 0

    project = _engine.project_dir()
    session_id = payload.get("session_id")
    owed = router_owed(project, session_id)
    from_tree = tree_owed(project, session_id)
    if not owed and not from_tree:
        return 0

    sections: list[str] = []
    if owed:
        sections.append(
            "roll-call: the turn ended with consults the router demanded still not "
            "on the ledger (full text in .claude/routing.toml):\n" + "\n".join(owed)
        )
    if from_tree:
        sections.append(
            "roll-call: files changed outside the editor tools match required "
            "rules with no fresh consult (full text in .claude/routing.toml):\n"
            + "\n".join(from_tree)
        )
    text = "\n".join(sections) + (
        "\nSpawn the seat, or say in the message why the consult is being skipped."
    )
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": text}},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
