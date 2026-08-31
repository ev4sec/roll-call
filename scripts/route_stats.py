#!/usr/bin/env python
"""Aggregate the router's fire-rate ledger into a spend report, offenders only.

**Why this is a script and not prose in the doctor command.** Correlating three
files against thresholds is mechanical, and mechanical work done by a model is
work done slightly differently every time, at a token price per run. The doctor
command invokes this with one Bash call and reports the lines it prints; the
raw ledgers never need to enter anyone's context.

Reads (all hook-written or project-owned):

    .claude/.route-stats    one line per router firing: rule_id, R|A, unix ts
    .claude/.consults       one line per agent run: name, unix ts
    .claude/routing.toml    which agents each rule names, and its level

Reports only what crosses a threshold, because a report that lists twenty
passing checks trains the reader to skim it:

  * A required rule that fired NOISY_FIRINGS or more times inside the window
    while none of its agents was consulted at all. That rule is being ignored,
    which is how rules get muted, and a muted rule takes the credible ones
    down with it. The named remedy is /roll-call:write-routing-rule, so
    de-escalation stays a human act made through the existing skill.
  * Documents growing in the most expensive read paths: agent-brief.md is
    read by every seat on every consult, agent-findings.md the same and
    append-only by design, and each seat definition is re-paid on every spawn
    of that seat.

Exit code is always 0. This is a report, not a gate.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

WINDOW_DAYS = 7
NOISY_FIRINGS = 10
BRIEF_BUDGET_WORDS = 1200
FINDINGS_BUDGET_WORDS = 2000
SEAT_BUDGET_WORDS = 2200


def _words(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").split())
    except OSError:
        return 0


def _timestamped_lines(path: Path, cutoff: float) -> list[list[str]]:
    """Tab-separated rows whose final field is a unix timestamp inside the window."""
    rows: list[list[str]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            fields = line.split("\t")
            try:
                if float(fields[-1]) >= cutoff:
                    rows.append(fields)
            except (ValueError, IndexError):
                continue
    except OSError:
        pass
    return rows


def report(project: Path, window_days: float) -> list[str]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - 3.10 and older
        return ["route stats: needs Python 3.11+ to read routing.toml."]

    claude = project / ".claude"
    try:
        with (claude / "routing.toml").open("rb") as fh:
            routing = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"route stats: routing table unreadable ({exc})."]

    cutoff = time.time() - window_days * 24 * 3600

    firings: dict[str, int] = {}
    for fields in _timestamped_lines(claude / ".route-stats", cutoff):
        if len(fields) == 3:
            firings[fields[0]] = firings.get(fields[0], 0) + 1

    consults: dict[str, int] = {}
    for fields in _timestamped_lines(claude / ".consults", cutoff):
        if len(fields) == 2:
            name = fields[0].strip()
            consults[name] = consults.get(name, 0) + 1

    lines: list[str] = []
    for rule in routing.get("rule", []):
        rid = str(rule.get("id", "?"))
        fired = firings.get(rid, 0)
        agents = [str(a) for a in rule.get("agents", [])]
        consulted = sum(consults.get(a, 0) for a in agents)
        if rule.get("level") == "required" and fired >= NOISY_FIRINGS and consulted == 0:
            lines.append(
                f"rule {rid}: fired {fired}x in {window_days:g}d with zero consults "
                f"of {', '.join(agents)}. It is being ignored, which is how rules "
                f"get muted. Narrow its globs, add an exclude, or demote it via "
                f"/roll-call:write-routing-rule."
            )

    brief = _words(claude / "agent-brief.md")
    if brief > BRIEF_BUDGET_WORDS:
        lines.append(
            f"agent-brief.md is {brief} words (budget {BRIEF_BUDGET_WORDS}): every "
            f"word is read by every seat on every consult. Trim it, or lift a "
            f"slow-path section into a file the brief points at instead."
        )

    findings = _words(claude / "agent-findings.md")
    if findings > FINDINGS_BUDGET_WORDS:
        lines.append(
            f"agent-findings.md is {findings} words (budget {FINDINGS_BUDGET_WORDS}) "
            f"and is read in full by every seat on every consult. Move unbuilt "
            f"verified findings into deletable findings-<seat>-<topic>.md files, "
            f"which is the ledger's own shipped mechanism. Never prune the "
            f"permanent record itself."
        )

    for seat in sorted((claude / "agents").glob("*.md")):
        seat_words = _words(seat)
        if seat_words > SEAT_BUDGET_WORDS:
            lines.append(
                f"agents/{seat.name} is {seat_words} words (budget "
                f"{SEAT_BUDGET_WORDS}): the definition is re-paid on every spawn "
                f"of that seat."
            )

    return lines or ["routing economics: nothing over threshold."]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=None,
                        help="Repo root. Defaults to CLAUDE_PROJECT_DIR or cwd.")
    parser.add_argument("--window-days", type=float, default=WINDOW_DAYS)
    args = parser.parse_args(argv)

    root = args.target or os.environ.get("CLAUDE_PROJECT_DIR") or "."
    project = Path(root).resolve()
    if not (project / ".claude").is_dir():
        print(f"route stats: no .claude/ under {project}; is roll-call set up here?")
        return 0

    for line in report(project, args.window_days):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
