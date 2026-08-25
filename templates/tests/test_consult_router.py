"""Does the router actually fire, and does it stay quiet when it should?

**A router that names an agent and never blocks is a vacuous guard**, and a
router that blocks on everything gets muted within a day. Every assertion here
therefore has its negative pole: a fresh consult must silence a rule, and an
unrelated file must never summon anyone.

Most of this file is portable and needs no edits. **The one section to fill in
is `THE_CHANGES_THAT_MUST_ROUTE`**, and it is the most valuable part.

**Its oracle should be history, not imagination.** On the origin project the
list was the exact set of paths touched during one session that shipped a
format bump moving DDL, split two modules, relicensed the project and changed
the agent roster: consulting zero agents, while the routing table named an
owner for every one of them. Written that way, the test does not ask "does the
matcher work"; it asks *"would it have caught that day?"* Until this project has
had such a day, seed the list from the paths whose owner you would most regret
skipping, and replace them with real history the first time routing is missed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _find_hook() -> Path | None:
    """Locate the router, which ships with the plugin rather than living here.

    The hooks used to sit at `.claude/hooks/` inside each project. They now ship
    read-only inside the roll-call plugin, so this test has to go looking. In
    order of reliability:

      1. `ROLL_CALL_HOOKS`, for a checkout or a non-standard install.
      2. `CLAUDE_PLUGIN_ROOT`, set when the harness runs this.
      3. The plugin cache under the user's Claude directory.

    Finding nothing is not a failure. It means the suite is being run somewhere
    the plugin is not installed, and a red test there would say "your routing is
    broken" when the truth is "the router is not here". The routing assertions
    below that need no subprocess still run.
    """
    override = os.environ.get("ROLL_CALL_HOOKS")
    if override and (Path(override) / "consult_router.py").is_file():
        return Path(override) / "consult_router.py"

    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root and (Path(plugin_root) / "hooks" / "consult_router.py").is_file():
        return Path(plugin_root) / "hooks" / "consult_router.py"

    cache = Path.home() / ".claude" / "plugins" / "cache"
    if cache.is_dir():
        found = sorted(cache.glob("*/roll-call/*/hooks/consult_router.py"))
        if found:
            return found[-1]
    return None


HOOK = _find_hook()

needs_hook = pytest.mark.skipif(
    HOOK is None,
    reason="roll-call plugin not found; set ROLL_CALL_HOOKS to its hooks/ directory",
)


def _load():  # type: ignore[no-untyped-def]
    if HOOK is None:
        return None
    spec = importlib.util.spec_from_file_location("consult_router", HOOK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


router = _load()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A repo skeleton carrying the real routing table, with an empty ledger."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "routing.toml").write_bytes(
        (ROOT / ".claude" / "routing.toml").read_bytes()
    )
    return tmp_path


def _consulted(project: Path, *agents: str, hours_ago: float = 0.0) -> None:
    stamp = time.time() - hours_ago * 3600
    (project / ".claude" / ".consults").write_text(
        "".join(f"{a}\t{stamp:.0f}\n" for a in agents), encoding="utf-8"
    )


# --------------------------------------------------------------------------
# INSTANTIATION: replace these with this project's real paths and owners. Each
# entry is "a change that must never be made without asking this seat".
# --------------------------------------------------------------------------
THE_CHANGES_THAT_MUST_ROUTE = [
    ("src/PROJECT_SLUG/models.py", "systems-architect"),
    ("src/PROJECT_SLUG/api/routes.py", "systems-architect"),
    ("src/PROJECT_SLUG/net/client.py", "security-engineer"),
    ("pyproject.toml", "security-engineer"),
    ("src/PROJECT_SLUG/report/render.py", "practitioner-critic"),
    ("LICENSE", "approval-judge"),
    ("CLAUDE.md", "approval-judge"),
    (".claude/roadmap.md", "commercial-strategist"),
    (".claude/slice.md", "scope-validator"),
]


@pytest.mark.parametrize(
    ("rel", "agent"),
    THE_CHANGES_THAT_MUST_ROUTE,
    ids=[f"{p}->{a}" for p, a in THE_CHANGES_THAT_MUST_ROUTE],
)
@needs_hook
def test_the_changes_that_must_route_do(rel: str, agent: str, project: Path) -> None:
    required, _ = router.owed(rel, project)
    owed_agents = {a for rule in required for a in rule["missing"]}
    assert agent in owed_agents, f"{rel} no longer routes to {agent}"


@needs_hook
def test_a_fresh_consult_silences_the_rule(project: Path) -> None:
    """**The negative pole.** A router that blocks after the consult is noise."""
    _consulted(project, "systems-architect")
    required, _ = router.owed("src/PROJECT_SLUG/models.py", project)
    assert not required


@needs_hook
def test_a_stale_consult_does_not_count(project: Path) -> None:
    """Freshness is the whole reason the ledger carries a timestamp."""
    _consulted(project, "systems-architect", hours_ago=48)
    required, _ = router.owed("src/PROJECT_SLUG/models.py", project)
    assert "systems-architect" in {a for rule in required for a in rule["missing"]}


@pytest.mark.parametrize(
    "rel",
    [
        "tests/conftest.py",
        "scripts/inspect_dist.py",
        ".claude/LESSONS.md",
        "docs/notes.txt",
    ],
)
@needs_hook
def test_ordinary_files_summon_nobody(rel: str, project: Path) -> None:
    """An alarm that cries wolf is worse than no alarm.

    `tests/**` is advisory by design and must never block; the rest match no
    rule at all.
    """
    required, _ = router.owed(rel, project)
    assert not required, f"{rel} blocks on a consult it should not need"


@needs_hook
def test_the_advisory_tier_does_not_block_but_is_reported(project: Path) -> None:
    required, advised = router.owed("tests/test_something.py", project)
    assert not required
    assert "test-strategist" in {a for rule in advised for a in rule["missing"]}


@needs_hook
def test_every_rule_names_agents_that_exist(project: Path) -> None:
    """A typo'd agent name is a rule that can never be satisfied.

    It would block the path forever, because no consult can ever match it: the
    exact shape of a guard that looks present and does the wrong thing.
    """
    _, rules = router._load_rules(project)
    roster = {p.stem for p in (ROOT / ".claude" / "agents").glob("*.md")}
    assert roster, "no agent definitions found; this test would be vacuous"
    for rule in rules:
        for agent in rule["agents"]:
            assert agent in roster, f"rule {rule['id']!r} names unknown agent {agent!r}"


@needs_hook
def test_every_seat_on_the_roster_has_a_trigger(project: Path) -> None:
    """**A seat with no routing rule can never be invoked by the mechanism.**

    On the origin project two seats were created, described, and given tools,
    and nothing would ever have summoned either of them. **A seat nobody asks is
    worse than no seat, because the roster reads as covered.**

    The complement of `test_every_rule_names_agents_that_exist`, which catches a
    rule pointing at nobody. Together they make the roster and the routing table
    each other's guard, which is the only thing that makes two files agree.
    """
    _, rules = router._load_rules(project)
    routed = {a for rule in rules for a in rule["agents"]}
    roster = {p.stem for p in (ROOT / ".claude" / "agents").glob("*.md")}
    assert roster, "no agent definitions found; this test would be vacuous"

    unrouted = sorted(roster - routed)
    assert not unrouted, (
        f"these seats exist and nothing routes to them: {unrouted}. Add a rule to "
        f".claude/routing.toml, or remove the seat. An agent the mechanism never "
        f"invokes is a roster entry pretending to be coverage."
    )


@needs_hook
def test_every_rule_states_a_question_and_a_cost(project: Path) -> None:
    """Routing that names an agent but not a question produces a survey.

    The Prime directive requires a recommendation stated as the thing to build.
    A rule with no question hands the agent nothing to answer.
    """
    _, rules = router._load_rules(project)
    for rule in rules:
        assert len(str(rule.get("question", "")).strip()) > 40, f"{rule['id']}: no real question"
        assert len(str(rule.get("why", "")).strip()) > 30, f"{rule['id']}: no stated cost"
        assert rule.get("level") in {"required", "advised"}, f"{rule['id']}: bad level"


@needs_hook
def test_the_hook_exits_two_and_says_who_to_ask(project: Path) -> None:
    """End to end through the real process, because that is what runs.

    Exit 2 is what puts the message in front of the session instead of into a
    log nobody reads.
    """
    # One string, not path components. The scaffold substitutes the literal
    # `src/PROJECT_SLUG` with the detected source root, and it can only see it
    # when it appears in the same single-string form routing.toml uses.
    target = project / "src/PROJECT_SLUG/models.py"
    payload = json.dumps({"tool_input": {"file_path": str(target)}})
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project), "PATH": ""},
    )
    assert result.returncode == 2, result.stderr
    assert "systems-architect" in result.stderr
    assert "PARALLEL" in result.stderr


@needs_hook
def test_a_broken_routing_table_fails_open(project: Path) -> None:
    """Unlike publish_guard, this one must not wedge the repository.

    `publish_guard` fails closed because an unknown state there means "might
    publish". Here an unreadable table means "cannot advise", and blocking every
    edit in the repo over a syntax error is a worse failure than missing a
    consult. It is loud instead.
    """
    (project / ".claude" / "routing.toml").write_text(
        "this is not [ valid toml", encoding="utf-8"
    )
    payload = json.dumps({"tool_input": {"file_path": str(project / "src" / "x.py")}})
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project), "PATH": ""},
    )
    assert result.returncode == 0
    assert "unreadable" in result.stderr
