"""The spend report exists to catch two silent curves: a required rule being
ignored at a per-edit token price, and the documents that grow in the most
expensive read paths. Both fail silently, which is this engine's least favorite
way to fail, so the script that watches them gets tests with negative poles:
quiet must mean healthy, never broken.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "route_stats.py"

ROUTING = """
[settings]
fresh_hours = 24

[[rule]]
id = "data-model"
paths = ["src/app/models.py"]
agents = ["systems-architect"]
level = "required"
question = "State the field."
why = "Schema changes are load-bearing."

[[rule]]
id = "new-tests"
paths = ["tests/**"]
agents = ["test-strategist"]
level = "advised"
question = "What would still be broken?"
why = "Coverage failures cost the most."
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    (claude / "agents").mkdir(parents=True)
    (claude / "routing.toml").write_text(ROUTING, encoding="utf-8")
    return tmp_path


def run(project: Path, *extra: str) -> str:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--target", str(project), *extra],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def stamp_firings(project: Path, rule: str, count: int, kind: str = "R") -> None:
    now = time.time()
    lines = "".join(f"{rule}\t{kind}\t{now:.0f}\n" for _ in range(count))
    path = project / ".claude" / ".route-stats"
    path.write_text(path.read_text(encoding="utf-8") + lines if path.exists() else lines,
                    encoding="utf-8")


def test_a_healthy_table_gets_one_line(project: Path) -> None:
    out = run(project)
    assert out.strip() == "routing economics: nothing over threshold."


def test_an_ignored_required_rule_is_reported(project: Path) -> None:
    stamp_firings(project, "data-model", 12)
    out = run(project)
    assert "rule data-model: fired 12x" in out
    assert "write-routing-rule" in out, "the remedy must be named"


def test_a_consulted_rule_is_not_an_offender(project: Path) -> None:
    """Firing often is fine when the consults actually happen."""
    stamp_firings(project, "data-model", 12)
    (project / ".claude" / ".consults").write_text(
        f"systems-architect\t{time.time():.0f}\n", encoding="utf-8"
    )
    out = run(project)
    assert "data-model" not in out


def test_a_noisy_advised_rule_is_not_an_offender(project: Path) -> None:
    """Advised rules never block, so their firings are not the muting hazard."""
    stamp_firings(project, "new-tests", 30, kind="A")
    out = run(project)
    assert "new-tests" not in out


def test_firings_outside_the_window_do_not_count(project: Path) -> None:
    old = time.time() - 10 * 24 * 3600
    lines = "".join(f"data-model\tR\t{old:.0f}\n" for _ in range(12))
    (project / ".claude" / ".route-stats").write_text(lines, encoding="utf-8")
    out = run(project)
    assert "data-model" not in out


def test_an_overgrown_findings_ledger_is_flagged_with_the_shipped_remedy(
    project: Path,
) -> None:
    (project / ".claude" / "agent-findings.md").write_text(
        "finding " * 2500, encoding="utf-8"
    )
    out = run(project)
    assert "agent-findings.md" in out
    assert "findings-<seat>-<topic>.md" in out, "name the diversion mechanism"
    assert "Never prune the permanent record" in out


def test_an_overgrown_brief_is_flagged(project: Path) -> None:
    (project / ".claude" / "agent-brief.md").write_text("word " * 1500, encoding="utf-8")
    out = run(project)
    assert "agent-brief.md is 1500 words" in out


def test_an_overgrown_seat_definition_is_flagged(project: Path) -> None:
    (project / ".claude" / "agents" / "systems-architect.md").write_text(
        "word " * 2500, encoding="utf-8"
    )
    out = run(project)
    assert "agents/systems-architect.md" in out


def test_a_repo_without_the_engine_says_so_instead_of_crashing(tmp_path: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--target", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0
    assert "is roll-call set up here" in proc.stdout


def test_a_corrupt_stats_file_degrades_to_healthy_not_a_crash(project: Path) -> None:
    (project / ".claude" / ".route-stats").write_text(
        "garbage with no tabs\nnot\ta\tnumber\n", encoding="utf-8"
    )
    out = run(project)
    assert "nothing over threshold" in out
