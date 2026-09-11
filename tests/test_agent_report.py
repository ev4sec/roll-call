"""The claim queue is written by machinery, or it is the honor system again.

**Why this file exists.** The findings ledger was the last record in the
engine that depended on a session remembering to write it. `agent_report.py`
closes that by queuing every labeled claim the moment a seat finishes. The
tests here hold it to the same discipline as the consult ledger: it records
what a seat said, it records the absence of labels rather than staying quiet
about it, it never records anything from a subagent that is not a seat, and
it never prunes, because a claim that expires unread is a claim nobody
checked.

Each assertion has its negative pole, as elsewhere: the hook that speaks
when it should is tested next to the hook that stays silent when it should.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "agent_report.py"
QUEUE = ".claude/.pending-findings"

sys.path.insert(0, str(ROOT / "hooks"))
import agent_report  # noqa: E402

REPORT = """# Review of the change

- [verified] `pytest tests/test_store.py` passes: 14 passed in 0.8s.
- The migration is reversible [reasoned]; nothing here has been run.
| claim | [measured] 0.10 ms per call on the CI runner |
Nothing else to report.
"""


def fire(project: Path, payload: object) -> subprocess.CompletedProcess:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK)],
        input=text, capture_output=True, text=True, timeout=60,
        env={"CLAUDE_PROJECT_DIR": str(project), "PATH": ""},
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    (claude / "agents").mkdir(parents=True)
    (claude / "engine.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (claude / "agents" / "security-engineer.md").write_text("---\nname: security-engineer\n---\n",
                                                             encoding="utf-8")
    return tmp_path


def stop(seat: str, message: str, **extra: object) -> dict:
    return {"hook_event_name": "SubagentStop", "agent_type": seat,
            "last_assistant_message": message, **extra}


def queue(project: Path) -> list[list[str]]:
    path = project / QUEUE
    if not path.is_file():
        return []
    return [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines()]


# ------------------------------------------------------------- extraction

def test_every_labeled_line_becomes_a_claim() -> None:
    found = agent_report.claims(REPORT)
    assert [label for label, _ in found] == ["verified", "reasoned", "measured"]


def test_the_claim_is_the_sentence_not_its_markdown() -> None:
    found = dict(agent_report.claims(REPORT))
    assert found["verified"].startswith("[verified] `pytest")
    assert not found["measured"].startswith("|"), "table pipes leaked into the claim"
    assert not found["measured"].endswith("|")


def test_labels_are_matched_regardless_of_case() -> None:
    assert agent_report.claims("[Verified] it runs") == [("verified", "[Verified] it runs")]


def test_a_long_claim_is_truncated_visibly() -> None:
    (label, claim), = agent_report.claims("[read] " + "x" * 600)
    assert len(claim) == agent_report.MAX_CLAIM_CHARS
    assert claim.endswith("...")


def test_a_report_with_no_labels_yields_one_row_saying_so() -> None:
    rows = agent_report.rows("seat", "Looks fine to me. Ship it.", None)
    assert len(rows) == 1
    assert rows[0][0] == "unlabeled"
    assert "no labeled claims" in rows[0][1]


def test_an_empty_report_yields_nothing() -> None:
    assert agent_report.rows("seat", "   \n", None) == []


def test_the_cap_is_announced_never_silent() -> None:
    many = "\n".join(f"[reasoned] claim {i}" for i in range(30))
    rows = agent_report.rows("seat", many, "/tmp/agent-abc.jsonl")
    assert len(rows) == agent_report.MAX_ROWS_PER_REPORT + 1
    label, text = rows[-1]
    assert label == "overflow"
    assert "10 further" in text
    assert "/tmp/agent-abc.jsonl" in text


# --------------------------------------------------------------- the hook

def test_a_seat_report_lands_in_the_queue(project: Path) -> None:
    result = fire(project, stop("security-engineer", REPORT))
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip(), "the hook must not speak; stdout goes to the subagent"
    rows = queue(project)
    assert len(rows) == 3
    stamp, seat, label, claim = rows[0]
    assert float(stamp) > 0
    assert seat == "security-engineer"
    assert label == "verified"
    assert "pytest" in claim


def test_rows_append_across_reports(project: Path) -> None:
    fire(project, stop("security-engineer", "[read] first"))
    fire(project, stop("security-engineer", "[read] second"))
    assert [r[3] for r in queue(project)] == ["[read] first", "[read] second"]


def test_a_subagent_that_is_not_a_seat_is_not_recorded(project: Path) -> None:
    """Explore runs and one-off helpers are not findings."""
    result = fire(project, stop("Explore", "[verified] found 12 endpoints"))
    assert result.returncode == 0
    assert not (project / QUEUE).exists()


def test_a_hostile_agent_name_cannot_escape_the_roster_directory(project: Path) -> None:
    (project / "elsewhere.md").write_text("", encoding="utf-8")
    result = fire(project, stop("../elsewhere", "[verified] x"))
    assert result.returncode == 0
    assert not (project / QUEUE).exists()


def test_separators_inside_a_claim_are_scrubbed(project: Path) -> None:
    fire(project, stop("security-engineer", "[asserted] a\tb"))
    rows = queue(project)
    assert len(rows) == 1 and len(rows[0]) == 4, "a tab in the claim broke the row"


def test_a_missing_message_is_survived(project: Path) -> None:
    result = fire(project, {"hook_event_name": "SubagentStop", "agent_type": "security-engineer"})
    assert result.returncode == 0
    assert not (project / QUEUE).exists()


def test_garbage_on_stdin_is_survived(project: Path) -> None:
    result = fire(project, "{not json")
    assert result.returncode == 0
    assert not result.stderr.strip()


def test_an_unconfigured_repository_gets_no_queue(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "security-engineer.md").write_text("", encoding="utf-8")
    result = fire(tmp_path, stop("security-engineer", "[verified] x"))
    assert result.returncode == 0
    assert not (tmp_path / QUEUE).exists()
