"""The mechanical half of doctor's checklist, now in `scripts/health.py`.

Each report prints only what is wrong, so the tests are mostly about the
negative pole: a healthy fixture gets one line, and each kind of defect gets
exactly the line that names it.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "scripts" / "scaffold.py"
sys.path.insert(0, str(ROOT / "scripts"))
import health  # noqa: E402


@pytest.fixture
def installed(tmp_path: Path) -> Path:
    (tmp_path / "src" / "acme").mkdir(parents=True)
    (tmp_path / "src" / "acme" / "models.py").write_text("x = 1\n", encoding="utf-8")
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCAFFOLD), "--project-name", "Acme", "--slug", "acme",
         "--source-root", "src/acme", "--target", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return tmp_path


def write_rules(project: Path, body: str) -> None:
    (project / ".claude" / "routing.toml").write_text(body, encoding="utf-8")


# ------------------------------------------------------------------- config --

def test_a_scaffolded_config_is_healthy(installed: Path) -> None:
    assert health.config_report(installed) == [
        "config: engine.toml parses and points at real paths."]


def test_template_values_and_missing_paths_are_named(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "engine.toml").write_text(
        '[project]\nname = "PROJECT_NAME"\nslug = "project_slug"\n'
        'source_root = "src/project_slug"\n\n[tests]\ndir = "nowhere"\n'
        'interpreter = "no-such-runner-xyz"\n', encoding="utf-8")
    lines = health.config_report(tmp_path)
    assert any("name still carries the template" in ln for ln in lines)
    assert any("slug still carries the template" in ln for ln in lines)
    assert any("source_root" in ln and "template" in ln for ln in lines)
    assert any("dir 'nowhere' does not exist" in ln for ln in lines)
    assert any("no-such-runner-xyz" in ln for ln in lines)


def test_an_unparseable_config_is_one_line(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "engine.toml").write_text("[project\n", encoding="utf-8")
    lines = health.config_report(tmp_path)
    assert len(lines) == 1 and "does not parse" in lines[0]


def test_a_missing_config_points_at_init(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    assert "Run /roll-call:init" in health.config_report(tmp_path)[0]


# -------------------------------------------------------------------- rules --

def test_dead_rules_are_named_and_live_ones_are_not(installed: Path) -> None:
    lines = health.rules_report(installed)
    dead = {ln.split(":")[0] for ln in lines if "matches no file" in ln}
    assert "rule public-interface" in dead
    assert "rule data-model" not in dead, "src/acme/models.py exists, so it is live"


def test_a_phantom_seat_is_named(installed: Path) -> None:
    write_rules(installed, '[[rule]]\nid = "ghost"\npaths = ["src/acme/models.py"]\n'
                           'agents = ["nobody-here"]\nlevel = "required"\n')
    lines = health.rules_report(installed)
    assert any("rule ghost: names seat 'nobody-here'" in ln for ln in lines)


def test_an_orphaned_exclude_is_a_hole(installed: Path) -> None:
    (installed / "src" / "acme" / "api").mkdir()
    (installed / "src" / "acme" / "api" / "routes.py").write_text("r = 1\n", encoding="utf-8")
    write_rules(installed,
                '[[rule]]\nid = "broad"\npaths = ["src/acme/**"]\nexclude = ["src/acme/api/**"]\n'
                'agents = ["systems-architect"]\nlevel = "required"\n')
    lines = health.rules_report(installed)
    assert any("rule broad: its exclude leaves 1 file(s) covered by no rule" in ln
               and "src/acme/api/routes.py" in ln for ln in lines)
    # Give the carved path an owner and the hole closes.
    write_rules(installed,
                '[[rule]]\nid = "broad"\npaths = ["src/acme/**"]\nexclude = ["src/acme/api/**"]\n'
                'agents = ["systems-architect"]\nlevel = "required"\n\n'
                '[[rule]]\nid = "api"\npaths = ["src/acme/api/**"]\n'
                'agents = ["systems-architect"]\nlevel = "required"\n')
    assert not any("covered by no rule" in ln for ln in health.rules_report(installed))


def test_an_overbroad_rule_is_named(installed: Path) -> None:
    for i in range(30):
        (installed / "src" / "acme" / f"m{i}.py").write_text("x = 1\n", encoding="utf-8")
    write_rules(installed, '[[rule]]\nid = "everything"\npaths = ["**"]\n'
                           'agents = ["systems-architect"]\nlevel = "required"\n')
    lines = health.rules_report(installed)
    assert any("rule everything: matches" in ln and "muted" in ln for ln in lines)


def test_unrouted_seats_and_an_all_advised_posture_are_named(installed: Path) -> None:
    write_rules(installed, '[[rule]]\nid = "m"\npaths = ["src/acme/models.py"]\n'
                           'agents = ["systems-architect"]\nlevel = "advised"\n')
    lines = health.rules_report(installed)
    assert any("seat security-engineer: no rule routes to it" in ln for ln in lines)
    assert any("posture: all 1 rule(s) are advised" in ln for ln in lines)


def test_a_healthy_table_gets_one_line(installed: Path) -> None:
    seats = sorted(p.stem for p in (installed / ".claude" / "agents").glob("*.md"))
    body = "".join(
        f'[[rule]]\nid = "r{i}"\npaths = ["src/acme/models.py"]\nagents = ["{seat}"]\n'
        f'level = "required"\n\n' for i, seat in enumerate(seats)
    )
    write_rules(installed, body)
    lines = health.rules_report(installed)
    assert len(lines) == 1 and lines[0].startswith("rules: ")


def test_a_missing_or_broken_table_is_one_line(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    assert health.rules_report(tmp_path) == ["routing.toml is missing; nothing routes."]
    (tmp_path / ".claude" / "routing.toml").write_text("[[rule\n", encoding="utf-8")
    assert "does not parse" in health.rules_report(tmp_path)[0]


# ------------------------------------------------------------- placeholders --

def test_placeholders_are_counted_per_file_and_seats_are_flagged(installed: Path) -> None:
    lines = health.placeholders_report(installed)
    assert lines[0].endswith("file(s):")
    assert any(ln.startswith("  .claude/vision.md:") and "blank record" in ln for ln in lines)
    assert any(ln.startswith("  .claude/agents/systems-architect.md:") for ln in lines)
    assert not any("TEMPLATE-NOTES.md" in ln for ln in lines)
    assert any("REFUSALS is empty" in ln and "does not block" in ln for ln in lines)


def test_a_filled_refusals_list_is_not_reported(installed: Path) -> None:
    test = installed / "tests" / "test_permanent_refusals.py"
    text = test.read_text(encoding="utf-8").replace(
        "REFUSALS: list[tuple[str, str]] = [",
        'REFUSALS: list[tuple[str, str]] = [\n    ("CLAUDE.md", "never"),')
    test.write_text(text, encoding="utf-8")
    assert not health.refusals_unfilled(test)
    assert not any("REFUSALS is empty" in ln for ln in health.placeholders_report(installed))


def test_no_placeholders_is_one_line(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# done\n", encoding="utf-8")
    assert health.placeholders_report(tmp_path) == ["placeholders: none left."]


# ------------------------------------------------------------------ ledgers --

def test_an_unwritten_ledger_and_an_empty_record_are_named(installed: Path) -> None:
    lines = health.ledgers_report(installed)
    assert any("no consult ledger yet" in ln for ln in lines)
    assert any("no verdict rows yet" in ln for ln in lines)
    assert any("scan-rules.toml" in ln for ln in lines)


def test_consults_crediting_no_seat_are_counted(installed: Path) -> None:
    now = time.time()
    (installed / ".claude" / ".consults").write_text(
        f"systems-architect\t{now:.0f}\nagent\t{now:.0f}\nExplore\t{now:.0f}\n", encoding="utf-8")
    lines = health.ledgers_report(installed, now=now)
    assert any("2 of 3 consult entries name no seat on the roster (Explore, agent)" in ln
               for ln in lines)
    assert not any("days ago" in ln for ln in lines)
    stale = health.ledgers_report(installed, now=now + 20 * 86400)
    assert any("the last consult was 20 days ago" in ln for ln in stale)


def test_a_queue_outside_gitignore_and_a_waiting_marker_are_named(installed: Path) -> None:
    claude = installed / ".claude"
    (claude / ".pending-findings").write_text("1\tseat\tread\tclaim\n", encoding="utf-8")
    (claude / ".gitignore").write_text(".consults\n", encoding="utf-8")
    (claude / ".agent-ran").write_text("12:00:00 systems-architect\n", encoding="utf-8")
    lines = health.ledgers_report(installed)
    assert any(".gitignore does not list .pending-findings" in ln for ln in lines)
    assert any("waiting for the commit guard" in ln for ln in lines)
    (claude / ".gitignore").write_text(".consults\n.pending-findings\n", encoding="utf-8")
    assert not any(".gitignore" in ln for ln in health.ledgers_report(installed))


def test_the_script_reports_all_four_blocks(installed: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "health.py"), "--target", str(installed)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    for block in ("[config]", "[rules]", "[placeholders]", "[ledgers]"):
        assert block in proc.stdout
