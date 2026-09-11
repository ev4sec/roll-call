#!/usr/bin/env python
"""Read the roster's track record and report the seats that need watching.

**Why this is a script and not prose in the doctor command.** The findings
ledger says what to look for in its own standing-observations section: a
seat whose claims hold in one domain and fail in another should be asked for
measurements more aggressively. That is a count over a table, and a count
done by a model is done slightly differently every time, at a token price
per run. Here it is done once, tested, and the doctor command reports the
lines.

Reads (both project-owned or hook-written):

    .claude/agent-findings.md     the permanent ledger, one table row per
                                  claim: date, seat, claim, verdict, ...
    .claude/.pending-findings     the queue agent_report.py writes: claims
                                  recorded by the hook and not yet judged

Reports only what crosses a threshold, because a report that lists every
seat's tally trains the reader to skim it:

  * A seat whose reproduced claims were refuted often enough that its next
    finding should be checked before it is believed. The number is the
    finding; the remedy is the brief's own rule, ask for the command.
  * A seat whose claims are mostly acted on without reproduction. The ledger
    calls UNVERIFIED its most useful category, and a seat living there is a
    seat whose track record cannot be trusted either way.
  * Claims still waiting in the queue, with the age of the oldest, because a
    queue nobody empties is the honor system wearing a hook's name.

Exit code is always 0. This is a report, not a gate. It never writes.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

VERDICTS = ("HELD", "REFUTED", "UNVERIFIED", "PARTIAL")
#: Fewer rows than this and a rate is noise, not a record.
MIN_ROWS = 5
REFUTED_SHARE = 0.4
UNVERIFIED_SHARE = 0.5
STALE_DAYS = 7


def _cells(line: str) -> list[str] | None:
    """The cells of a markdown table row, or None for anything else."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if all(set(c) <= set("-: ") for c in cells):
        return None  # the separator row
    return cells


def ledger_rows(text: str) -> list[tuple[str, str]]:
    """(seat, verdict) for every filled-in row of the ledger table.

    The template's placeholder row carries `{{`, and the header row carries
    no verdict; both are skipped. A verdict is the first recognized word in
    the cell, so `HELD (partially)` counts as HELD and a free-text cell
    counts as nothing.
    """
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        cells = _cells(line)
        if cells is None or len(cells) < 4 or "{{" in line:
            continue
        seat, verdict_cell = cells[1], cells[3].upper()
        verdict = next((v for v in VERDICTS if v in verdict_cell), None)
        if verdict is None or seat.lower() == "seat":
            continue
        rows.append((seat.strip("`"), verdict))
    return rows


def pending_rows(text: str) -> list[tuple[float, str]]:
    """(timestamp, seat) for every well-formed row of the queue."""
    out: list[tuple[float, str]] = []
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) != 4:
            continue
        try:
            out.append((float(fields[0]), fields[1]))
        except ValueError:
            continue
    return out


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def report(project: Path, now: float | None = None) -> list[str]:
    claude = project / ".claude"
    now = time.time() if now is None else now
    lines: list[str] = []

    tallies: dict[str, dict[str, int]] = {}
    for seat, verdict in ledger_rows(_read(claude / "agent-findings.md")):
        tallies.setdefault(seat, {v: 0 for v in VERDICTS})[verdict] += 1

    for seat in sorted(tallies):
        t = tallies[seat]
        total = sum(t.values())
        if total < MIN_ROWS:
            continue
        judged = t["HELD"] + t["REFUTED"]
        if judged and t["REFUTED"] / judged >= REFUTED_SHARE:
            lines.append(
                f"seat {seat}: {t['REFUTED']} of {judged} reproduced claims were "
                f"refuted. Check its next finding before believing it, and ask "
                f"for the command with the claim; the brief already requires it."
            )
        if t["UNVERIFIED"] / total >= UNVERIFIED_SHARE:
            lines.append(
                f"seat {seat}: {t['UNVERIFIED']} of {total} claims were acted on "
                f"without reproduction. Its track record cannot say whether it "
                f"is usually right. Reproduce the next one before building on it."
            )

    pending = pending_rows(_read(claude / ".pending-findings"))
    if pending:
        oldest = min(stamp for stamp, _ in pending)
        age_days = max(0.0, (now - oldest) / 86400)
        seats = sorted({seat for _, seat in pending})
        noun, verb = ("claim", "awaits") if len(pending) == 1 else ("claims", "await")
        line = (
            f"{len(pending)} {noun} from {', '.join(seats)} {verb} a verdict in "
            f".claude/.pending-findings"
        )
        if age_days >= STALE_DAYS:
            line += f"; the oldest has waited {age_days:.0f} days"
        line += (
            ". Each row is a claim a hook recorded and nobody has judged: give "
            "it a verdict in agent-findings.md and delete the row, or delete "
            "the row after reading it."
        )
        lines.append(line)

    if lines:
        return lines
    if not tallies:
        return ["seat track record: no verdicts in agent-findings.md yet."]
    return ["seat track record: nothing over threshold."]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=None,
                        help="Repo root. Defaults to CLAUDE_PROJECT_DIR or cwd.")
    args = parser.parse_args(argv)

    root = args.target or os.environ.get("CLAUDE_PROJECT_DIR") or "."
    project = Path(root).resolve()
    if not (project / ".claude").is_dir():
        print(f"seat stats: no .claude/ under {project}; is roll-call set up here?")
        return 0

    for line in report(project):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
