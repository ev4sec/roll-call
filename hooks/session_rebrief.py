#!/usr/bin/env python
"""SessionStart hook: tell a rebuilt context what the engine's ledgers hold.

**Why this exists.** The failure this whole plugin was built around is an
instruction that was read at session start and gone by the third edit. A
compaction is a session start in the middle of the work. The context is
summarized, the summary keeps what it keeps, and everything the engine had
established with the session up to that point is at the mercy of a summary
nobody reviewed: which consults the router had demanded and were still owed,
which seats had already been asked so they are not asked twice, which agents
had edited the tree without anyone reading the diff, and which of their
claims were still waiting for a verdict.

Every one of those facts is in a file the hooks wrote. None of them was read
back at the moment the session most needed them, because nothing fired then.
This hook fires then. It also fires on a resume, a fork, a clear, and a plain
startup, since each of those is a context that does not remember the last
one, and the ledgers do.

**It speaks only when there is state.** A repository with no owed consults,
no unreviewed agent edits, and no queued claims gets nothing, because the
constitution and the procedure are already loaded and a hook that repeats
them is the alarm that gets muted. The brief is a handful of lines and every
line names a file where the full record lives.

**Where each line comes from.**

  consults still owed   the router's per-session stamp of rules that fired,
                        re-checked against the consult ledger now. Only
                        present when the harness gave the session an id and
                        a data directory, which is the same condition under
                        which the router compresses repeats.
  consulted recently    the consult ledger inside `fresh_hours`, so a rebuilt
                        session does not pay for a round it already ran.
  unreviewed edits      the marker `agent_watch.py` writes and the commit
                        guard clears.
  claims awaiting       the queue `agent_report.py` writes.

Plain text on stdout, which the harness adds to the session's context for
this event. Never blocks, always exits 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _engine
import consult_router
import unreviewed_agent_edits

PENDING = ".claude/.pending-findings"
MARKER = ".claude/.agent-ran"
ADVISED_PREFIX = "advised:"


def owed_lines(project: Path, session_id: object) -> tuple[list[str], list[str]]:
    """(rules still owed this session, seats consulted inside the window).

    Both come from the router's own readers, so this hook cannot disagree
    with the router about what counts as fresh or which rule is which.
    """
    if consult_router.tomllib is None:
        return [], []
    seen = {
        key for key in consult_router._seen_rules(
            consult_router._state_file(project, session_id)
        )
        if not key.startswith(ADVISED_PREFIX)
    }
    try:
        settings, rules = consult_router._load_rules(project)
    except (OSError, consult_router.tomllib.TOMLDecodeError):
        return [], []
    try:
        window = float(settings.get("fresh_hours", 24))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        window = 24.0
    fresh = consult_router._fresh_consults(project, window)

    owed: list[str] = []
    for rule in rules:
        if consult_router._rule_key(rule) not in seen:
            continue
        missing = [str(a) for a in rule.get("agents", []) if str(a) not in fresh]
        if missing:
            owed.append(f"  [{rule.get('id', '?')}] -> {', '.join(missing)}")
    consulted = [f"{name} ({window:g}h window)" for name in sorted(fresh)]
    return owed, consulted


def marker_line(project: Path) -> str | None:
    try:
        text = (project / MARKER).read_text(encoding="utf-8")
    except OSError:
        return None
    agents, files = unreviewed_agent_edits.read_marker(text)
    if not agents:
        return None
    names = sorted({label.split(" ", 1)[-1] for label in agents})
    if files is None:
        touched = "the source root"
    elif not files:
        return None
    else:
        touched = ", ".join(files)
    return (
        f"Agents edited the tree since the last commit and the diff has not "
        f"been reviewed: {', '.join(names)} touched {touched}. The commit "
        f"guard will show it; reading it first is cheaper."
    )


def pending_line(project: Path) -> str | None:
    try:
        lines = (project / PENDING).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    seats: set[str] = set()
    count = 0
    for line in lines:
        fields = line.split("\t")
        if len(fields) == 4:
            count += 1
            seats.add(fields[1])
    if not count:
        return None
    noun, verb = ("claim", "awaits") if count == 1 else ("claims", "await")
    return (
        f"{count} {noun} from {', '.join(sorted(seats))} {verb} a verdict in "
        f"{PENDING}. That is the reproduction list: give each a verdict in "
        f".claude/agent-findings.md and delete its row, or delete the row "
        f"after reading it."
    )


def brief(project: Path, session_id: object, source: object) -> str:
    owed, consulted = owed_lines(project, session_id)
    sections: list[str] = []
    if owed:
        sections.append(
            "Consults the router demanded earlier in this session, still not on "
            "the ledger (full text in .claude/routing.toml):\n" + "\n".join(owed)
        )
    marker = marker_line(project)
    if marker:
        sections.append(marker)
    pending = pending_line(project)
    if pending:
        sections.append(pending)
    if not sections:
        return ""
    if consulted:
        sections.append("Already consulted: " + ", ".join(consulted) + ".")
    how = str(source) if isinstance(source, str) and source else "startup"
    head = f"roll-call: the context was rebuilt ({how}). What the ledgers hold:"
    return head + "\n\n" + "\n\n".join(sections) + "\n"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if not _engine.have_project_dir() or not _engine.initialized():
        return 0

    project = _engine.project_dir()
    text = brief(project, payload.get("session_id"), payload.get("source"))
    if text:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
