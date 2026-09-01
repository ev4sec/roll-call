"""The scaffold writes into a stranger's repository, so it gets held to that.

**The promise the README makes, in the user's own words:** "Nothing gets
overwritten." That sentence is the reason someone is willing to run a command
that touches fifteen files in a repo they care about, and it is worth more than
any feature here. Every collision case below is a way that promise could break
quietly.

**Why idempotence has its own tests.** Running init twice is not an exotic case.
People re-run setup commands when they are unsure whether the first one worked,
which is exactly when a second run is most likely to do damage. The first
version of this script appended a duplicate `@import` to its own output on the
second run, and nothing caught it until it was run three times by hand.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "scripts" / "scaffold.py"
IMPORT_LINE = "@.claude/operating-procedure.md"


def run(target: Path, *extra: str, name: str = "Acme", slug: str = "acme") -> dict:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCAFFOLD), "--project-name", name, "--slug", slug,
         "--target", str(target), "--json", *extra],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def imports(claude_md: Path) -> int:
    return sum(
        1 for line in claude_md.read_text(encoding="utf-8").splitlines()
        if line.strip() == IMPORT_LINE
    )


def test_a_fresh_repo_gets_the_whole_engine(tmp_path: Path) -> None:
    report = run(tmp_path)
    assert not report["skipped"]
    assert (tmp_path / ".claude" / "routing.toml").is_file()
    assert (tmp_path / ".claude" / "engine.toml").is_file()
    assert (tmp_path / "CLAUDE.md").is_file()
    assert len(list((tmp_path / ".claude" / "agents").glob("*.md"))) == 9


def test_the_agents_land_where_the_user_can_edit_them(tmp_path: Path) -> None:
    """Project-local, not plugin-local.

    This is the whole reason the roster is a template. Agents in a plugin cache
    are read-only, and a seat that cannot be taught about the codebase gives
    generic advice forever.
    """
    run(tmp_path)
    seat = tmp_path / ".claude" / "agents" / "systems-architect.md"
    assert seat.is_file()
    seat.write_text(seat.read_text(encoding="utf-8") + "\nlocal note\n",
                    encoding="utf-8")
    assert "local note" in seat.read_text(encoding="utf-8")


def test_mechanical_placeholders_are_filled(tmp_path: Path) -> None:
    run(tmp_path, name="Acme", slug="acme")
    blob = "".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in tmp_path.rglob("*.md")
    )
    assert "{{PROJECT}}" not in blob
    assert "Acme" in blob
    # The bare uppercase form shipped unsubstituted once: the dict knew
    # `{{PROJECT_SLUG}}` and `project_slug` but routing.toml and the seeded
    # tests use `PROJECT_SLUG`, so scaffolded repos got routing rules aimed at
    # `src/PROJECT_SLUG/...`, paths that exist nowhere.
    assert "PROJECT_SLUG" not in blob
    routing = (tmp_path / ".claude" / "routing.toml").read_text(encoding="utf-8")
    assert "PROJECT_SLUG" not in routing


def test_the_detected_source_root_reaches_the_config(tmp_path: Path) -> None:
    """`--source-root` was accepted and silently ignored once.

    The config told the hooks the code lived at `src/<slug>` regardless of
    where it actually lived, and the post-agent diff guard watched the wrong
    directory as a result.
    """
    run(tmp_path, "--source-root", "lib/acme")
    conf = (tmp_path / ".claude" / "engine.toml").read_text(encoding="utf-8")
    assert 'source_root = "lib/acme"' in conf
    assert "src/acme" not in conf


def test_judgment_placeholders_survive_untouched(tmp_path: Path) -> None:
    """They must stay visible.

    A silently defaulted vision statement produces a document that is
    authoritative and wrong, and the gates read it as though someone meant it.
    """
    report = run(tmp_path)
    assert report["judgment_slots"] > 0
    vision = (tmp_path / ".claude" / "vision.md").read_text(encoding="utf-8")
    assert "{{" in vision


def test_an_existing_claude_md_is_appended_to_never_replaced(tmp_path: Path) -> None:
    original = "# My Project\n\nRules I wrote myself.\n"
    (tmp_path / "CLAUDE.md").write_text(original, encoding="utf-8")
    report = run(tmp_path)
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert text.startswith(original), "the user's own file must survive verbatim"
    assert IMPORT_LINE in text, "and the engine must still be reachable"
    assert report["appended"]


def test_existing_agents_are_left_completely_alone(tmp_path: Path) -> None:
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "systems-architect.md").write_text("mine, tuned\n", encoding="utf-8")
    report = run(tmp_path)
    assert (agents / "systems-architect.md").read_text(encoding="utf-8") == "mine, tuned\n"
    assert any("systems-architect" in s for s in report["skipped"])
    assert (agents / "test-strategist.md").is_file(), "the rest still arrive"


@pytest.mark.parametrize("runs", [2, 3])
def test_running_it_again_changes_nothing(tmp_path: Path, runs: int) -> None:
    for _ in range(runs):
        report = run(tmp_path)
    assert not report["written"], "a second run must write nothing"
    assert not report["appended"]
    assert imports(tmp_path / "CLAUDE.md") == 1, "duplicate imports are the bug"


def test_running_it_again_over_a_users_own_claude_md(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# Mine\n", encoding="utf-8")
    run(tmp_path)
    run(tmp_path)
    assert imports(tmp_path / "CLAUDE.md") == 1


def test_dry_run_writes_absolutely_nothing(tmp_path: Path) -> None:
    report = run(tmp_path, "--dry-run")
    assert report["written"], "it still reports what it would do"
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / "CLAUDE.md").exists()


def test_the_test_directory_is_configurable(tmp_path: Path) -> None:
    """A repo that keeps tests in `spec/` should not sprout a `tests/`.

    And engine.toml must record the choice: it used to keep `dir = "tests"`
    regardless, so the test hook watched a directory that did not exist and
    the drift check looked for the installed test files in the wrong place.
    """
    run(tmp_path, "--test-dir", "spec")
    assert list((tmp_path / "spec").glob("test_*.py"))
    assert not (tmp_path / "tests").exists()
    conf = (tmp_path / ".claude" / "engine.toml").read_text(encoding="utf-8")
    assert 'dir = "spec"' in conf, "the config must say where the tests went"


def test_the_project_side_suite_is_installed(tmp_path: Path) -> None:
    """Including the one that fails on purpose.

    `test_permanent_refusals.py` refuses to pass until the project writes down
    what it will not do. Shipping the engine without it would mean shipping a
    green suite that asserts nothing.
    """
    run(tmp_path)
    names = {p.name for p in (tmp_path / "tests").glob("*.py")}
    assert "test_permanent_refusals.py" in names
    assert "test_consult_router.py" in names
    assert "test_doc_contract.py" in names


def test_a_missing_target_is_refused_not_created(tmp_path: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCAFFOLD), "--project-name", "X", "--slug", "x",
         "--target", str(tmp_path / "nope")],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 1
    assert not (tmp_path / "nope").exists()


def test_installer_guidance_is_lifted_out_of_the_hot_path(tmp_path: Path) -> None:
    """Template notes must not ride along in files agents load constantly.

    `agent-brief.md` is opened by all nine seats on every round and each agent
    definition is loaded on every invocation of that seat. Guidance addressed to
    whoever fills the template in is dead weight there, paid forever.
    """
    run(tmp_path)
    claude = tmp_path / ".claude"
    for name in ("agent-brief.md", "slice.md", "vision.md", "operating-procedure.md"):
        assert "INSTANTIATION" not in (claude / name).read_text(encoding="utf-8")
    for agent in (claude / "agents").glob("*.md"):
        assert "INSTANTIATION" not in agent.read_text(encoding="utf-8")


def test_the_constitution_is_the_most_important_one_to_strip(tmp_path: Path) -> None:
    """`CLAUDE.md` is auto-loaded every session, so a comment there is read
    on every turn by everything. It was missed once."""
    run(tmp_path)
    assert "INSTANTIATION" not in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")


def test_nothing_is_actually_discarded(tmp_path: Path) -> None:
    """Lifted, not deleted. The guidance is still useful to a person."""
    report = run(tmp_path)
    notes = tmp_path / ".claude" / "TEMPLATE-NOTES.md"
    assert notes.is_file()
    assert report["notes_lifted"] > 20
    text = notes.read_text(encoding="utf-8")
    assert "agent-brief.md" in text and "operating-procedure.md" in text


def test_the_notes_file_is_not_regenerated_over_an_edited_one(tmp_path: Path) -> None:
    run(tmp_path)
    notes = tmp_path / ".claude" / "TEMPLATE-NOTES.md"
    notes.write_text("my own notes\n", encoding="utf-8")
    run(tmp_path)
    assert notes.read_text(encoding="utf-8") == "my own notes\n"
