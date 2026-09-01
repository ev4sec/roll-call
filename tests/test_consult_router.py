"""The consult router's token-burn controls, driven through the real process.

Covers repeat compression (the full why/question prose renders once per rule
per session, later firings still exit 2 with a one-line demand), per-rule
excludes (a broad glob yields to the narrower owning rule), the advised
once-flag, and the fire-rate stats ledger.

The negative poles matter most and get their own tests: every fallback must
fail toward verbosity (today's full block), never toward silence, because a
router that goes quiet is the founding failure of this plugin reintroduced by
a token optimization.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "consult_router.py"

QUESTION_DM = "State the field, its type, nullability, and the cost to change later."
QUESTION_FE = "How should this be built in the browser, and what happens at scale?"
QUESTION_PI = "State the contract as the thing to build."

ROUTING = f"""
[settings]
fresh_hours = 24
max_parallel = 4

[[rule]]
id = "data-model"
paths = ["src/app/models.py"]
agents = ["systems-architect"]
level = "required"
why = "Schema changes are load-bearing and expensive to reverse."
question = "{QUESTION_DM}"

[[rule]]
id = "frontend"
paths = ["**/*.ts"]
exclude = ["src/app/api/**"]
agents = ["frontend-architect"]
level = "required"
why = "Browser architecture is owned."
question = "{QUESTION_FE}"

[[rule]]
id = "public-interface"
paths = ["src/app/api/**"]
agents = ["systems-architect"]
level = "required"
why = "Interface contracts are owned."
question = "{QUESTION_PI}"
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    claude = tmp_path / "repo" / ".claude"
    claude.mkdir(parents=True)
    (claude / "routing.toml").write_text(ROUTING, encoding="utf-8")
    return tmp_path / "repo"


@pytest.fixture
def plugin_data(tmp_path: Path) -> Path:
    data = tmp_path / "plugin-data"
    data.mkdir()
    return data


def fire(
    project: Path,
    edited: str,
    session_id: object = "sess-alpha",
    plugin_data: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    payload: dict[str, object] = {
        "tool_input": {"file_path": str(project / edited)},
    }
    if session_id is not None:
        payload["session_id"] = session_id
    env = {"CLAUDE_PROJECT_DIR": str(project), "PATH": ""}
    if os.environ.get("SYSTEMROOT"):
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    if plugin_data is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


# ------------------------------------------------------- A2: repeat compression

def test_first_firing_renders_the_full_block(project: Path, plugin_data: Path) -> None:
    result = fire(project, "src/app/models.py", plugin_data=plugin_data)
    assert result.returncode == 2
    assert "CONSULT OWED for src/app/models.py: systems-architect" in result.stderr
    assert "why:" in result.stderr
    assert QUESTION_DM in result.stderr, "first firing must carry the question"


def test_repeat_firing_compresses_but_still_blocks(project: Path, plugin_data: Path) -> None:
    first = fire(project, "src/app/models.py", plugin_data=plugin_data)
    second = fire(project, "src/app/models.py", plugin_data=plugin_data)
    assert second.returncode == 2, "enforcement must fire on every repeat"
    assert "CONSULT OWED" in second.stderr
    assert "systems-architect" in second.stderr, "short form must name the agent"
    assert "data-model" in second.stderr, "short form must name the rule id"
    assert "routing.toml" in second.stderr, "recovery pointer for compacted sessions"
    assert QUESTION_DM not in second.stderr, "question prose must not repeat"
    assert len(second.stderr) < len(first.stderr) / 3, (
        f"compression too weak: {len(first.stderr)} -> {len(second.stderr)} chars"
    )


def test_every_repeat_still_exits_2(project: Path, plugin_data: Path) -> None:
    for i in range(5):
        result = fire(project, "src/app/models.py", plugin_data=plugin_data)
        assert result.returncode == 2, f"firing {i + 1} did not block"
        assert "CONSULT OWED" in result.stderr


def test_a_new_session_gets_the_full_block_again(project: Path, plugin_data: Path) -> None:
    fire(project, "src/app/models.py", session_id="sess-alpha", plugin_data=plugin_data)
    fresh = fire(project, "src/app/models.py", session_id="sess-beta", plugin_data=plugin_data)
    assert fresh.returncode == 2
    assert QUESTION_DM in fresh.stderr, "restart or resume must re-teach in full"


def test_missing_plugin_data_falls_back_to_full_every_time(project: Path) -> None:
    for _ in range(2):
        result = fire(project, "src/app/models.py", plugin_data=None)
        assert result.returncode == 2
        assert QUESTION_DM in result.stderr, "no state dir must mean today's behavior"


def test_missing_session_id_falls_back_to_full_every_time(
    project: Path, plugin_data: Path
) -> None:
    for _ in range(2):
        result = fire(project, "src/app/models.py", session_id=None, plugin_data=plugin_data)
        assert result.returncode == 2
        assert QUESTION_DM in result.stderr


def test_repeat_style_full_restores_old_behavior(project: Path, plugin_data: Path) -> None:
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing = routing.replace("fresh_hours = 24", 'fresh_hours = 24\nrepeat_style = "full"')
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    for _ in range(3):
        result = fire(project, "src/app/models.py", plugin_data=plugin_data)
        assert result.returncode == 2
        assert QUESTION_DM in result.stderr


def test_a_rule_unseen_this_session_gets_its_full_stanza(
    project: Path, plugin_data: Path
) -> None:
    """Compression is per rule, not per session: a newly matching rule teaches
    in full even while an already-seen rule compresses in the same message."""
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    mixed = fire(project, "src/app/api/handler.py", plugin_data=plugin_data)
    # handler.py matches public-interface only; its first firing must be full.
    assert mixed.returncode == 2
    assert QUESTION_PI in mixed.stderr
    repeat = fire(project, "src/app/api/handler.py", plugin_data=plugin_data)
    assert QUESTION_PI not in repeat.stderr
    assert "public-interface" in repeat.stderr


def test_a_fresh_consult_still_silences_everything(project: Path, plugin_data: Path) -> None:
    """The ledger, not the compression state, is what ends the loop."""
    ledger = project / ".claude" / ".consults"
    ledger.write_text(f"systems-architect\t{time.time()}\n", encoding="utf-8")  # project: allow py-sql-fstring - consult ledger line, not SQL
    result = fire(project, "src/app/models.py", plugin_data=plugin_data)
    assert result.returncode == 0
    assert result.stderr.strip() == ""


def test_stale_session_stamps_are_pruned(project: Path, plugin_data: Path) -> None:
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    store = plugin_data / "router-seen"
    old = store / "deadbeefdeadbeef-sess-ancient.json"
    old.write_text("[]", encoding="utf-8")
    ancient = time.time() - 72 * 3600
    os.utime(old, (ancient, ancient))
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    assert not old.exists(), "stamps older than the TTL must be dropped"
    assert list(store.glob("*.json")), "the live session's stamp must survive"


def test_a_hostile_session_id_cannot_escape_the_store(
    project: Path, plugin_data: Path
) -> None:
    """Non-vacuous by construction: the assertion is on the stamp's own name.

    Scanning the store for escaped files cannot work (a path that escaped is
    not under the store), so instead assert the one stamp that was written
    landed inside the store under a fully sanitized name. Deleting the
    sanitization makes the name carry separators, which either lands the file
    elsewhere or fails the pattern; both fail this test.
    """
    result = fire(
        project,
        "src/app/models.py",
        session_id="../../../../etc/passwd",
        plugin_data=plugin_data,
    )
    assert result.returncode == 2
    store = plugin_data / "router-seen"
    stamps = list(store.iterdir()) if store.is_dir() else []
    assert len(stamps) == 1, "the sanitized stamp must land inside the store"
    name = stamps[0].name
    assert re.fullmatch(r"[0-9a-f]{16}-[A-Za-z0-9_-]+\.json", name), name
    assert "etcpasswd" in name, "sanitization should keep the survivable chars"


def test_the_breadth_warning_survives_compression(
    project: Path, plugin_data: Path
) -> None:
    """max_parallel counts every agent owed on the edit, in every branch.

    The warning exists for exactly the broad, repeatedly-edited changes that
    produce repeat firings, so compressing a repeat must never compress it.
    """
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing += """
[[rule]]
id = "broad"
paths = ["src/app/models.py"]
agents = ["a-one", "a-two", "a-three", "a-four", "a-five"]
level = "required"
why = "Breadth check."
question = "Too many seats at once."
"""
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    first = fire(project, "src/app/models.py", plugin_data=plugin_data)
    repeat = fire(project, "src/app/models.py", plugin_data=plugin_data)
    for result in (first, repeat):
        assert result.returncode == 2
        assert "too broad to route" in result.stderr, (
            "the breadth warning must fire on full and compressed renders alike"
        )


def test_id_less_rules_do_not_alias_each_other(
    project: Path, plugin_data: Path
) -> None:
    """Two rules without ids must not share one seen-key.

    Aliasing would classify rule B's very first firing as a repeat of rule A
    and swallow its why/question unseen: a first-firing degrade toward less
    output, which the fail-open discipline forbids. And a rule without an id
    must degrade the label to '?', never crash the hook (exit 1 drops
    enforcement entirely).
    """
    routing = """
[settings]
fresh_hours = 24

[[rule]]
paths = ["src/alpha/**"]
agents = ["seat-alpha"]
level = "required"
why = "Alpha lane."
question = "The alpha question, shown in full on first firing."

[[rule]]
paths = ["src/beta/**"]
agents = ["seat-beta"]
level = "required"
why = "Beta lane."
question = "The beta question, shown in full on first firing."
"""
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    first = fire(project, "src/alpha/core.py", plugin_data=plugin_data)
    second = fire(project, "src/beta/core.py", plugin_data=plugin_data)
    assert first.returncode == 2 and second.returncode == 2
    assert "The alpha question" in first.stderr
    assert "The beta question" in second.stderr, (
        "an id-less rule's first firing was treated as another rule's repeat"
    )
    repeat = fire(project, "src/beta/core.py", plugin_data=plugin_data)
    assert repeat.returncode == 2
    assert "The beta question" not in repeat.stderr, "its own repeat still compresses"


def test_advised_once_survives_repeat_style_full(
    project: Path, plugin_data: Path
) -> None:
    """The repeat_style knob restores full required blocks; routing.toml
    documents the advised "mentioned once" unconditionally, so the two must
    not be coupled."""
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing = routing.replace(
        "fresh_hours = 24", 'fresh_hours = 24\nrepeat_style = "full"'
    ).replace(
        'level = "required"\nwhy = "Interface contracts are owned."',
        'level = "advised"\nwhy = "Interface contracts are owned."',
    )
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    first = fire(project, "src/app/api/handler.py", plugin_data=plugin_data)
    second = fire(project, "src/app/api/handler.py", plugin_data=plugin_data)
    assert "consult advised" in first.stderr
    assert second.stderr.strip() == "", "mentioned once means once, whatever the knob"


# ------------------------------------------------------------- A3: excludes

def test_exclude_carves_the_overlap_out(project: Path, plugin_data: Path) -> None:
    """A .ts file under the api tree summons only the owning seat."""
    result = fire(project, "src/app/api/client.ts", plugin_data=plugin_data)
    assert result.returncode == 2
    assert "public-interface" in result.stderr
    assert "frontend-architect" not in result.stderr, (
        "excluded rule still demanded its seat: the duplicate spawn survives"
    )


def test_exclude_leaves_other_paths_untouched(project: Path, plugin_data: Path) -> None:
    result = fire(project, "src/web/app.ts", plugin_data=plugin_data)
    assert result.returncode == 2
    assert "frontend-architect" in result.stderr
    assert QUESTION_FE in result.stderr


def test_a_rule_without_exclude_behaves_exactly_as_before(
    project: Path, plugin_data: Path
) -> None:
    result = fire(project, "src/app/models.py", plugin_data=plugin_data)
    assert result.returncode == 2
    assert "systems-architect" in result.stderr


# ------------------------------------------------- fail-open discipline holds

def test_malformed_stamp_file_falls_back_to_full(project: Path, plugin_data: Path) -> None:
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    store = plugin_data / "router-seen"
    for stamp in store.glob("*.json"):
        stamp.write_text("{not json", encoding="utf-8")
    result = fire(project, "src/app/models.py", plugin_data=plugin_data)
    assert result.returncode == 2
    assert QUESTION_DM in result.stderr, "unreadable state must mean full block"


# -------------------------------------- suffix gate vs explicit .md targets

def test_an_exactly_named_md_file_fires_its_rule(
    project: Path, plugin_data: Path
) -> None:
    """The 0.1.0 defect this closes: shipped rules named doc files that the
    suffix gate dropped before matching, so the board, roadmap, vision, and
    constitution gates could never fire while looking present."""
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing += """
[[rule]]
id = "board"
paths = [".claude/board.md"]
agents = ["scope-checker"]
level = "required"
why = "Scope arrives as a board line."
question = "Should this move onto the bench now?"
"""
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    result = fire(project, ".claude/board.md", plugin_data=plugin_data)
    assert result.returncode == 2
    assert "scope-checker" in result.stderr
    assert "Should this move onto the bench now?" in result.stderr


def test_a_glob_over_an_ignored_suffix_still_never_fires(
    project: Path, plugin_data: Path
) -> None:
    """Only equality overrides the gate. A glob rule over .md would re-fire
    on every doc edit in the tree, the exact churn the gate exists to stop."""
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing += """
[[rule]]
id = "all-docs"
paths = ["**/*.md"]
agents = ["doc-owner"]
level = "required"
why = "Docs matter."
question = "Is this doc right?"
"""
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    result = fire(project, "docs/notes.md", plugin_data=plugin_data)
    assert result.returncode == 0
    assert result.stderr.strip() == ""


def test_unnamed_doc_and_lockfile_churn_stays_silent(
    project: Path, plugin_data: Path
) -> None:
    """Non-vacuous: glob rules COVER each churn file, so silence proves the
    gate, not the absence of a matching rule."""
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing += """
[[rule]]
id = "doc-globs"
paths = ["**/*.md", "**/*.lock", "**/*.txt"]
agents = ["doc-owner"]
level = "required"
why = "Covers every churn file below, through globs only."
question = "Is this right?"
"""
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    for rel in ("README.md", "poetry.lock", "docs/notes.txt", "docs/NOTES.MD"):
        result = fire(project, rel, plugin_data=plugin_data)
        assert result.returncode == 0, f"{rel} summoned someone through a glob"
        assert result.stderr.strip() == ""


def test_literal_entries_survive_spelling_variants(
    project: Path, plugin_data: Path
) -> None:
    """A backslash or a leading ./ in a literal entry must not silently kill
    the gate override; that would be the dead-guard failure one spelling
    away from the feature."""
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing += """
[[rule]]
id = "board"
paths = ["./.claude/board.md"]
agents = ["scope-checker"]
level = "required"
why = "Scope arrives as a board line."
question = "Should this move onto the bench now?"

[[rule]]
id = "notes"
paths = [".claude\\\\notes.md"]
agents = ["note-owner"]
level = "required"
why = "Notes carry decisions."
question = "Is this decision recorded right?"
"""
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    board = fire(project, ".claude/board.md", plugin_data=plugin_data)
    notes = fire(project, ".claude/notes.md", plugin_data=plugin_data)
    assert board.returncode == 2, "a leading ./ must not kill the literal match"
    assert "scope-checker" in board.stderr
    assert notes.returncode == 2, "a backslash must not kill the literal match"
    assert "note-owner" in notes.stderr


def test_an_explicit_md_rule_gets_repeat_compression_too(
    project: Path, plugin_data: Path
) -> None:
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing += """
[[rule]]
id = "board"
paths = [".claude/board.md"]
agents = ["scope-checker"]
level = "required"
why = "Scope arrives as a board line."
question = "Should this move onto the bench now?"
"""
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    fire(project, ".claude/board.md", plugin_data=plugin_data)
    repeat = fire(project, ".claude/board.md", plugin_data=plugin_data)
    assert repeat.returncode == 2
    assert "Should this move onto the bench now?" not in repeat.stderr
    assert "scope-checker" in repeat.stderr


# ------------------------------------------------- advised: once per session

def test_advised_prints_once_per_session(project: Path, plugin_data: Path) -> None:
    """routing.toml documents advised as "mentioned once"; make it true."""
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing = routing.replace(
        'level = "required"\nwhy = "Interface contracts are owned."',
        'level = "advised"\nwhy = "Interface contracts are owned."',
    )
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    first = fire(project, "src/app/api/handler.py", plugin_data=plugin_data)
    second = fire(project, "src/app/api/handler.py", plugin_data=plugin_data)
    assert first.returncode == 0
    assert "consult advised" in first.stderr
    assert second.returncode == 0
    assert second.stderr.strip() == "", "advised must not repeat within a session"
    fresh = fire(
        project, "src/app/api/handler.py", session_id="sess-two", plugin_data=plugin_data
    )
    assert "consult advised" in fresh.stderr, "a new session is mentioned again"


def test_advised_still_prints_every_time_without_state(project: Path) -> None:
    """No plugin data dir means today's behavior, not silence."""
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing = routing.replace(
        'level = "required"\nwhy = "Interface contracts are owned."',
        'level = "advised"\nwhy = "Interface contracts are owned."',
    )
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    for _ in range(2):
        result = fire(project, "src/app/api/handler.py", plugin_data=None)
        assert "consult advised" in result.stderr


# ----------------------------------------------------- fire-rate stats ledger

def test_firings_land_in_the_stats_ledger(project: Path, plugin_data: Path) -> None:
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    stats = (project / ".claude" / ".route-stats").read_text(encoding="utf-8")
    lines = [ln for ln in stats.splitlines() if ln.startswith("data-model\tR\t")]
    assert len(lines) == 2, f"expected two R firings on the ledger, got:\n{stats}"


def test_stats_prune_past_the_window_once_the_file_is_large(
    project: Path, plugin_data: Path
) -> None:
    """Appends never rewrite (two parallel routers must not lose each other's
    lines), so the window prune triggers on size instead of on every write."""
    ancient = time.time() - 40 * 24 * 3600
    stats = project / ".claude" / ".route-stats"
    filler = "".join(
        f"old-rule\tR\t{ancient:.0f}\n" for _ in range(13000)  # project: allow py-sql-fstring - stats ledger line, not SQL
    )
    stats.write_text(filler, encoding="utf-8")
    assert stats.stat().st_size > 256 * 1024, "fixture must exceed the prune cap"
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    text = stats.read_text(encoding="utf-8")
    assert "old-rule" not in text, "entries past the window must be dropped"
    assert "data-model\tR\t" in text


def test_small_stats_files_are_appended_not_rewritten(
    project: Path, plugin_data: Path
) -> None:
    recent = time.time() - 3600
    stats = project / ".claude" / ".route-stats"
    stats.write_text(f"other-rule\tR\t{recent:.0f}\n", encoding="utf-8")  # project: allow py-sql-fstring - stats ledger line, not SQL
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    text = stats.read_text(encoding="utf-8")
    assert "other-rule" in text, "an append must preserve other processes' lines"
    assert "data-model\tR\t" in text


def test_hostile_rule_ids_cannot_corrupt_the_stats_format(
    project: Path, plugin_data: Path
) -> None:
    """Rule ids are user-authored TOML; a tab inside one would make its line
    unparseable and its firings silently uncountable."""
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing = routing.replace('id = "data-model"', 'id = "data\\tmodel"')
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    for line in (project / ".claude" / ".route-stats").read_text(
        encoding="utf-8"
    ).splitlines():
        assert len(line.split("\t")) == 3, f"corrupted stats line: {line!r}"


def test_stats_off_writes_nothing(project: Path, plugin_data: Path) -> None:
    routing = (project / ".claude" / "routing.toml").read_text(encoding="utf-8")
    routing = routing.replace("fresh_hours = 24", "fresh_hours = 24\nstats = false")
    (project / ".claude" / "routing.toml").write_text(routing, encoding="utf-8")
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    assert not (project / ".claude" / ".route-stats").exists()


def test_a_quiet_edit_records_no_stats(project: Path, plugin_data: Path) -> None:
    """The ledger records demands, not edits; a non-matching edit leaves no line."""
    result = fire(project, "src/other/util.py", plugin_data=plugin_data)
    assert result.returncode == 0
    assert not (project / ".claude" / ".route-stats").exists()
