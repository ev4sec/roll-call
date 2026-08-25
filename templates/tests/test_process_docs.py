"""The process machinery has to be reachable, or it does not govern.

`operating-procedure.md` states the failure this file guards, and states it as
something that already happened: *"Check that the audience actually reads the
file you filed it in. This rule exists because it was broken the day after it
was written: the measurement traps were recorded in this document, and no agent
is instructed to read this document: subagents get their own definition, not
the session's imports. The lesson was filed and still never arrived."*

It happened a second time with a state-of-the-project assessment that was
written carefully and referenced by nothing an agent or a session opens. It
would have been rediscovered by re-deriving it in chat, which is exactly what it
was written to prevent.

So reachability is now asserted rather than intended. **A document under
`.claude/` either has a path from something guaranteed to be read, or it does
not exist as far as this project is concerned.**

**What this cannot check** is whether the content is *current*. The board was
reachable, read, and wrong for a day. It listed shipped work as upcoming. No
test catches that; only updating it at a slice boundary does.

This file is part of the portable engine and should need no edits at
instantiation.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROCESS = ROOT / ".claude"

#: Documents guaranteed to be read, and therefore able to make others reachable.
#:
#: * `CLAUDE.md` is auto-loaded into every primary session.
#: * `operating-procedure.md` is imported by it, so it inherits that guarantee.
#: * `agent-brief.md` is the first thing every agent definition instructs.
#:
#: Nothing else qualifies. Being mentioned in a file nobody opens is the
#: failure, not the fix.
ENTRY_POINTS = (
    ROOT / "CLAUDE.md",
    PROCESS / "operating-procedure.md",
    PROCESS / "agent-brief.md",
)

#: Documents that are deliberately unreachable, and must stay that way.
#:
#: `TEMPLATE-NOTES.md` holds the guidance that shipped inside the engine
#: templates, lifted out when they were written here. Being unreferenced is the
#: entire point: `agent-brief.md` is opened by all nine seats on every round and
#: each agent definition is loaded on every invocation, so leaving that guidance
#: inline meant paying for it on every consult, forever. It is written for a
#: person, it is read when a person wants it, and nothing should point an agent
#: at it.
#:
#: Adding to this list is a real decision. An exemption granted casually is how
#: this test stops meaning anything.
DELIBERATELY_UNREFERENCED = {"TEMPLATE-NOTES.md"}


def _entry_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in ENTRY_POINTS)


def _process_documents() -> list[Path]:
    docs = sorted(PROCESS.glob("*.md")) + [PROCESS / "routing.toml"]
    return [d for d in docs if d.is_file()]


def test_the_entry_points_all_exist() -> None:
    """Negative pole. A renamed entry point would make every check below vacuous."""
    for path in ENTRY_POINTS:
        assert path.is_file(), f"{path} is missing; reachability cannot be judged"
    assert len(_entry_text()) > 5000


@pytest.mark.parametrize("doc", _process_documents(), ids=lambda p: p.name)
def test_every_process_document_is_reachable(doc: Path) -> None:
    """A document nothing points at is a document nothing obeys."""
    if doc.resolve() in {p.resolve() for p in ENTRY_POINTS}:
        return
    if doc.name in DELIBERATELY_UNREFERENCED:
        pytest.skip(f"{doc.name} is unreferenced on purpose")
    assert doc.name in _entry_text(), (
        f"{doc.name} is not named in CLAUDE.md, operating-procedure.md or "
        f"agent-brief.md, so nothing that is guaranteed to be read points at it. "
        f"Either reference it from one of those, or delete it. A finding recorded "
        f"somewhere that does not govern is not operative."
    )


@pytest.mark.parametrize(
    "agent", sorted((PROCESS / "agents").glob("*.md")), ids=lambda p: p.stem
)
def test_every_agent_is_told_to_read_the_brief(agent: Path) -> None:
    """The brief carries the measurement traps and the claim-labeling protocol.

    A seat that does not open it answers without the labels, and an unlabeled
    claim is treated as `[asserted]`, so the seat's whole output drops in value
    on its first use, silently.
    """
    text = agent.read_text(encoding="utf-8")
    assert "agent-brief.md" in text, (
        f"{agent.stem} is never told to read the standing brief, so it will "
        f"answer without the claim labels and without the known measurement traps."
    )


@pytest.mark.parametrize(
    "agent", sorted((PROCESS / "agents").glob("*.md")), ids=lambda p: p.stem
)
def test_every_agent_declares_what_it_is_not_for(agent: Path) -> None:
    """Six seats become fifteen pairwise "which one?" boundaries; nine become 36.

    Routing is decided under uncertainty, so a seat that does not say where its
    lane ends makes every neighboring seat harder to route to. Each definition
    carries an explicit hand-off section for that reason.
    """
    text = agent.read_text(encoding="utf-8").lower()
    assert "not for" in text or "does not" in text, (
        f"{agent.stem} never says what it is *not* for, so its boundary with the "
        f"other seats is undefined."
    )


def test_the_roster_the_brief_describes_is_the_roster_that_exists() -> None:
    """The brief tells each agent who else is being asked in parallel.

    A stale list there means a seat answers believing a domain is uncovered when
    it is owned, which is how two seats both decline the same question.
    """
    brief = (PROCESS / "agent-brief.md").read_text(encoding="utf-8")
    roster = sorted(p.stem for p in (PROCESS / "agents").glob("*.md"))
    assert roster, "no agents found; this test would be vacuous"
    missing = [name for name in roster if name not in brief]
    assert not missing, f"agent-brief.md does not mention {missing}"


def test_the_routing_table_parses_and_is_not_empty() -> None:
    """`consult_router.py` fails open on an unreadable table, by design.

    That is right for a hook: a syntax error must not wedge every edit in the
    repository, but it means a malformed table disables routing *silently*.
    This is the check that makes the failure loud somewhere.
    """
    with (PROCESS / "routing.toml").open("rb") as fh:
        data = tomllib.load(fh)
    assert data.get("rule"), "routing.toml parses but defines no rules; routing is off"
    assert data.get("settings", {}).get("fresh_hours")


def test_the_engine_config_parses() -> None:
    """The hooks fall back to defaults on a broken `engine.toml`, deliberately.

    Same reasoning as the routing table: a hook that dies takes its guard with
    it. That makes a typo here silent, so it is caught loudly in the suite
    instead.
    """
    path = PROCESS / "engine.toml"
    if not path.is_file():
        pytest.skip("engine.toml is optional; hooks run on defaults without it")
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    assert data.get("project", {}).get("slug"), "engine.toml names no project slug"
    assert data.get("project", {}).get("source_root"), "engine.toml names no source root"
