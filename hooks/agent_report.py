#!/usr/bin/env python
"""SubagentStop hook: queue every labeled claim a seat made, for a verdict.

**Why this exists.** The findings ledger, `.claude/agent-findings.md`, is the
roster's track record: what each seat claimed and whether it survived
reproduction. It is also the one ledger in this engine that was still written
on the honor system. The consult ledger stopped depending on anyone
remembering in 0.1.0, for the reason the router's own docstring gives: a
record kept by remembering is read at session start and forgotten by the
third edit. The findings ledger kept depending on it, because until now no
hook could see what a seat had actually said.

This hook can. It fires when a subagent finishes and receives the text of
its final response. It pulls out every claim the seat labeled per the brief
(`[verified]`, `[measured]`, `[read]`, `[reasoned]`, `[asserted]`) and
appends each one to `.claude/.pending-findings`, timestamped and named. The
verdict column is left to the session, because a hook cannot know whether a
claim reproduced. What it can guarantee is that the claim is on a list before
anyone decides whether to check it, which is the half of the record that was
being lost.

**What the queue is for.** The brief says a claim that would change what gets
built, carrying no reproduction, does not get acted on. The queue is that
list, written by machinery. Each row leaves it in one of two ways: it becomes
a ledger row with a verdict, or it is dropped by a person who read it. Nothing
here prunes it, because a claim that expires unread is a claim nobody
checked, and that is the state this hook exists to make visible.

**A seat that labels nothing gets one row saying so.** The brief treats an
unlabeled claim as `[asserted]`, and a report with no labels at all is a seat
not following its brief. That is worth one line in the queue rather than
silence, which would look like a seat that made no claims.

**Only the roster is recorded.** A subagent whose name is not a file in
`.claude/agents/` is not a seat, and its output is not a finding. Explore
runs and one-off helpers leave nothing here.

Produces no output and never blocks. The harness delivers this hook's stdout
to the subagent rather than to the session, so nothing is printed; the
session learns what is queued from `session_rebrief.py`, from
`/roll-call:doctor`, and from the reconcile-board skill.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import _engine

PENDING = ".claude/.pending-findings"
AGENTS = ".claude/agents"

#: The labels the brief mandates, matched case-insensitively.
LABEL = re.compile(r"\[(verified|measured|read|reasoned|asserted)\]", re.IGNORECASE)
#: Leading list markers, heading marks, blockquotes and table pipes, so the
#: recorded claim is the sentence rather than its markdown.
DECORATION = re.compile(r"^[\s>#*\-+|]*(?:\d+[.)]\s*)?")
SEAT_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

#: A report is capped at this many rows so one verbose seat cannot flood the
#: queue; the cap is announced in the queue itself, never applied silently.
MAX_ROWS_PER_REPORT = 20
MAX_CLAIM_CHARS = 240


def _clean(line: str) -> str:
    text = DECORATION.sub("", line).strip()
    text = " ".join(text.split())
    if len(text) > MAX_CLAIM_CHARS:
        text = text[: MAX_CLAIM_CHARS - 3].rstrip() + "..."
    return text


def claims(text: str) -> list[tuple[str, str]]:
    """(label, claim) for every labeled line in a report, in order.

    A line's label is the first one it carries. Trailing pipes from a table
    row are dropped so the claim reads as prose.
    """
    found: list[tuple[str, str]] = []
    for raw in text.splitlines():
        match = LABEL.search(raw)
        if not match:
            continue
        cleaned = _clean(raw).rstrip("| ").strip()
        if cleaned:
            found.append((match.group(1).lower(), cleaned))
    return found


def rows(seat: str, text: str, transcript: object) -> list[tuple[str, str]]:
    """What goes into the queue for one report: the claims, or the absence."""
    words = len(text.split())
    if words == 0:
        return []
    labeled = claims(text)
    if not labeled:
        return [(
            "unlabeled",
            f"no labeled claims in a report of {words} words; the brief treats "
            f"every claim in it as [asserted]",
        )]
    if len(labeled) <= MAX_ROWS_PER_REPORT:
        return labeled
    dropped = len(labeled) - MAX_ROWS_PER_REPORT
    where = f" at {transcript}" if isinstance(transcript, str) and transcript else ""
    kept = labeled[:MAX_ROWS_PER_REPORT]
    kept.append((
        "overflow",
        f"{dropped} further labeled claims from {seat} were not recorded; "
        f"the full report is in the subagent transcript{where}",
    ))
    return kept


def _scrub(field: str) -> str:
    """Tabs and newlines are the queue's separators; a claim may carry neither."""
    return field.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if not _engine.initialized():
        return 0

    seat = payload.get("agent_type")
    if not isinstance(seat, str) or not SEAT_NAME.match(seat):
        return 0
    project = _engine.project_dir()
    if not (project / AGENTS / f"{seat}.md").is_file():
        return 0

    message = payload.get("last_assistant_message")
    if not isinstance(message, str):
        return 0

    queued = rows(seat, message, payload.get("agent_transcript_path"))
    if not queued:
        return 0

    stamp = f"{time.time():.0f}"
    lines = "".join(
        f"{stamp}\t{seat}\t{label}\t{_scrub(claim)}\n" for label, claim in queued
    )
    try:
        target = project / PENDING
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(lines)
    except OSError:
        # A queue that cannot be written leaves the record where it was
        # before this hook existed: in the session's memory. Never a crash.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
