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
    result = fire(
        project,
        "src/app/models.py",
        session_id="../../../../etc/passwd",
        plugin_data=plugin_data,
    )
    assert result.returncode == 2
    written = [p for p in plugin_data.rglob("*") if p.is_file()]
    for path in written:
        assert plugin_data in path.parents, f"stamp escaped the store: {path}"


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


def test_stats_prune_past_the_window_on_write(project: Path, plugin_data: Path) -> None:
    ancient = time.time() - 40 * 24 * 3600
    stats = project / ".claude" / ".route-stats"
    stats.write_text(f"old-rule\tR\t{ancient:.0f}\n", encoding="utf-8")  # project: allow py-sql-fstring - stats ledger line, not SQL
    fire(project, "src/app/models.py", plugin_data=plugin_data)
    text = stats.read_text(encoding="utf-8")
    assert "old-rule" not in text, "entries past the window must be dropped"
    assert "data-model\tR\t" in text


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
