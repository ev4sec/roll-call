"""The track record has a mechanical reader, with the same two poles as the
spend report: quiet means healthy, never broken, and every threshold is
tested from both sides.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "seat_stats.py"

sys.path.insert(0, str(ROOT / "scripts"))
import seat_stats  # noqa: E402

HEADER = (
    "# Ledger\n\n"
    "| Date | Seat | Claim | Verdict | Reproduction | What the error was |\n"
    "|---|---|---|---|---|---|\n"
    "| {{YYYY-MM-DD}} | {{seat}} | {{claim}} | {{HELD/REFUTED/UNVERIFIED}} | {{command}} | {{for refuted}} |\n"
)


def row(seat: str, verdict: str) -> str:
    return f"| 2026-09-01 | `{seat}` | a claim | {verdict} | ran it | - |\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    return tmp_path


def write_ledger(project: Path, *rows: str) -> None:
    (project / ".claude" / "agent-findings.md").write_text(HEADER + "".join(rows), encoding="utf-8")


def run(project: Path) -> str:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--target", str(project)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


# ---------------------------------------------------------------- parsing

def test_the_template_placeholder_row_and_the_header_are_not_rows() -> None:
    assert seat_stats.ledger_rows(HEADER) == []


def test_a_verdict_is_the_first_recognized_word_in_its_cell() -> None:
    rows = seat_stats.ledger_rows(HEADER + "| d | s | c | HELD (in part) | r | e |\n"
                                  "| d | s | c | see notes | r | e |\n")
    assert rows == [("s", "HELD")]


def test_backticks_around_a_seat_name_are_dropped() -> None:
    assert seat_stats.ledger_rows(HEADER + row("x", "REFUTED")) == [("x", "REFUTED")]


def test_malformed_queue_rows_are_skipped() -> None:
    assert seat_stats.pending_rows("1\tseat\tlabel\tclaim\nnope\nx\ta\tb\tc\n") == [(1.0, "seat")]


# ------------------------------------------------------------- thresholds

def test_an_empty_ledger_says_so_in_one_line(project: Path) -> None:
    write_ledger(project)
    assert run(project).strip() == "seat track record: no verdicts in agent-findings.md yet."


def test_a_healthy_ledger_gets_one_line(project: Path) -> None:
    write_ledger(project, *[row("systems-architect", "HELD")] * 6)
    assert run(project).strip() == "seat track record: nothing over threshold."


def test_a_seat_refuted_often_is_named(project: Path) -> None:
    write_ledger(project, *[row("security-engineer", "REFUTED")] * 3,
                 *[row("security-engineer", "HELD")] * 3)
    out = run(project)
    assert "seat security-engineer: 3 of 6 reproduced claims were refuted" in out


def test_too_few_rows_is_noise_not_a_record(project: Path) -> None:
    write_ledger(project, *[row("security-engineer", "REFUTED")] * 4)
    assert "refuted" not in run(project)


def test_a_seat_mostly_unverified_is_named(project: Path) -> None:
    write_ledger(project, *[row("practitioner-critic", "UNVERIFIED")] * 4,
                 row("practitioner-critic", "HELD"))
    out = run(project)
    assert "seat practitioner-critic: 4 of 5 claims were acted on without reproduction" in out


def test_unverified_below_half_is_not_named(project: Path) -> None:
    write_ledger(project, *[row("practitioner-critic", "UNVERIFIED")] * 2,
                 *[row("practitioner-critic", "HELD")] * 3)
    assert "without reproduction" not in run(project)


# ------------------------------------------------------------- the queue

def test_queued_claims_are_reported_with_their_seats(project: Path) -> None:
    now = f"{time.time():.0f}"
    (project / ".claude" / ".pending-findings").write_text(
        f"{now}\tsecurity-engineer\tverified\t[verified] a\n"
        f"{now}\tsystems-architect\treasoned\t[reasoned] b\n", encoding="utf-8")
    out = run(project)
    assert "2 claims from security-engineer, systems-architect await a verdict" in out
    assert "oldest has waited" not in out


def test_a_stale_queue_names_the_age_of_the_oldest_row(project: Path) -> None:
    old = f"{time.time() - 10 * 86400:.0f}"
    (project / ".claude" / ".pending-findings").write_text(
        f"{old}\tsecurity-engineer\tverified\t[verified] a\n", encoding="utf-8")
    out = run(project)
    assert "1 claim from security-engineer awaits a verdict" in out
    assert "the oldest has waited 10 days" in out


def test_a_missing_claude_directory_is_a_readable_answer(tmp_path: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--target", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0
    assert "is roll-call set up here?" in proc.stdout
