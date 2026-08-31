"""The drift check replaces a model-side comparison that could pull 30k+ words
into context; the price of that replacement is that the script must not lie.
Two lies are possible: reporting instantiation differences as drift (noise
that trains the reader to skim), and reporting a tuned file as clean (a real
divergence swallowed). Both get tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DRIFT = ROOT / "scripts" / "drift.py"
SCAFFOLD = ROOT / "scripts" / "scaffold.py"


@pytest.fixture
def installed(tmp_path: Path) -> Path:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCAFFOLD), "--project-name", "Acme", "--slug", "acme",
         "--source-root", "src/acme", "--target", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return tmp_path


def run(project: Path) -> str:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(DRIFT), "--target", str(project)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_a_fresh_install_reports_no_drift(installed: Path) -> None:
    """Substitutions and lifted notes must not read as divergence."""
    out = run(installed)
    assert "drifted:" not in out, out
    assert "never installed:" not in out, out
    assert "match the shipped templates" in out


def test_a_tuned_file_is_reported_with_direction(installed: Path) -> None:
    brief = installed / ".claude" / "agent-brief.md"
    brief.write_text(brief.read_text(encoding="utf-8") + "\nlocal tuning\n",
                     encoding="utf-8")
    out = run(installed)
    assert "drifted: .claude/agent-brief.md" in out
    assert "local-only" in out


def test_a_never_installed_template_is_named(installed: Path) -> None:
    """The exact signal an old install needs when a new template ships."""
    (installed / ".claude" / "parked-roles.md").unlink()
    out = run(installed)
    assert "never installed: .claude/parked-roles.md" in out


def test_the_merged_constitution_is_not_compared(installed: Path) -> None:
    (installed / "CLAUDE.md").write_text("# Entirely mine now\n", encoding="utf-8")
    out = run(installed)
    assert "CLAUDE.md" not in out, "a merged file must never be reported as drift"


def test_a_repo_without_the_engine_says_so_instead_of_crashing(tmp_path: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(DRIFT), "--target", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0
    assert "is roll-call set up here" in proc.stdout
