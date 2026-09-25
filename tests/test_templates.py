"""The scaffold has to be internally consistent before it is copied anywhere.

`/roll-call:init` writes `templates/` into a stranger's repository. Whatever is
wrong in here is wrong in every install, and it is wrong in a place the user
will reasonably assume was checked.

**The specific failure this guards.** The routing table names the seat that owns
each path. If it names a seat with no definition, the router does its job
perfectly and summons somebody who does not exist. That is worse than no
routing, because the block is real and the remedy is impossible. It has already
happened once on the origin project, which is why `templates/routing.toml`
carries the rule that a rule must name a seat that exists.

The reverse matters too, though less: a seat nothing routes to is a nine-file
roster pretending to be busier than it is.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
AGENTS = TEMPLATES / "agents"
ROUTING = TEMPLATES / "routing.toml"

#: Documents init writes into `.claude/`. Anything referencing these is fine.
SCAFFOLD = {
    "engine.toml", "routing.toml", "operating-procedure.md", "agent-brief.md",
    "measurement-traps.md", "agent-findings.md", "slice.md", "vision.md",
    "roadmap.md", "architecture.md", "security-invariants.md", "LESSONS.md",
    "parked-roles.md",
}


def routing() -> dict:
    return tomllib.loads(ROUTING.read_text(encoding="utf-8"))


def roster() -> set[str]:
    return {p.stem for p in AGENTS.glob("*.md")}


def routed_seats() -> set[str]:
    return {str(a) for rule in routing()["rule"] for a in rule["agents"]}


def test_the_roster_is_the_expected_size() -> None:
    assert len(roster()) == 9, sorted(roster())


def test_every_routed_seat_has_a_definition() -> None:
    """A rule naming a seat that does not exist summons nobody, loudly."""
    phantom = sorted(routed_seats() - roster())
    assert not phantom, f"routing.toml names seats with no agent file: {phantom}"


def test_every_seat_is_routed_to() -> None:
    idle = sorted(roster() - routed_seats())
    assert not idle, f"agents exist that no rule ever summons: {idle}"


def test_every_rule_has_an_id_paths_a_level_and_a_question() -> None:
    """Routing that names an agent but not a question produces a survey.

    The engine's whole premise is a recommendation stated as the thing to build,
    and a rule with no question cannot produce one.
    """
    for rule in routing()["rule"]:
        rid = rule.get("id", "<unnamed>")
        assert rule.get("paths"), f"{rid}: no paths"
        assert rule.get("agents"), f"{rid}: no agents"
        assert rule.get("level") in {"required", "advised"}, f"{rid}: bad level"
        assert rule.get("question", "").strip(), f"{rid}: no question"
        assert rule.get("why", "").strip(), f"{rid}: no cost-of-skipping"


def test_rule_ids_are_unique() -> None:
    ids = [rule.get("id") for rule in routing()["rule"]]
    assert len(ids) == len(set(ids)), "duplicate rule ids"


def test_the_settings_block_is_present() -> None:
    settings = routing()["settings"]
    assert settings["fresh_hours"] > 0
    assert settings["max_parallel"] > 0


@pytest.mark.parametrize("agent", sorted(p.name for p in AGENTS.glob("*.md")))
def test_every_agent_has_frontmatter_with_a_matching_name(agent: str) -> None:
    text = (AGENTS / agent).read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{agent}: no frontmatter"
    head = text.split("---", 2)[1]
    match = re.search(r"^name:\s*(\S+)", head, re.MULTILINE)
    assert match, f"{agent}: no name in frontmatter"
    assert match.group(1) == agent[:-3], f"{agent}: name does not match filename"
    assert re.search(r"^description:", head, re.MULTILINE), f"{agent}: no description"


@pytest.mark.parametrize("agent", sorted(p.name for p in AGENTS.glob("*.md")))
def test_every_agent_preloads_the_brief(agent: str) -> None:
    """The brief is the one document every seat carries, which is what makes
    it work. It is preloaded through the `skills` list rather than read on
    instruction, and the instruction stays as the fallback for an install
    whose brief is not yet a skill.
    """
    text = (AGENTS / agent).read_text(encoding="utf-8")
    head = text.split("---", 2)[1]
    assert "- agent-brief" in head, f"{agent}: skills list does not preload the brief"
    assert "skills/agent-brief/SKILL.md" in text, f"{agent}: no fallback path to the brief"


@pytest.mark.parametrize("agent", sorted(p.name for p in AGENTS.glob("*.md")))
def test_every_agent_declares_effort_and_memory(agent: str) -> None:
    """Effort follows the standard of evidence. Memory is the seat's own notes,
    and it turns on Write and Edit, so only a seat that already holds Bash gets
    it: a seat defined as never touching the tree must not gain the tools to."""
    head = (AGENTS / agent).read_text(encoding="utf-8").split("---", 2)[1]
    assert re.search(r"^effort: (low|medium|high|xhigh|max)$", head, re.MULTILINE), agent
    tools = re.search(r"^tools: (.*)$", head, re.MULTILINE).group(1)
    has_memory = bool(re.search(r"^memory: project$", head, re.MULTILINE))
    assert has_memory == ("Bash" in tools), f"{agent}: memory grant does not match Bash grant"


def test_the_constitution_imports_the_operating_procedure() -> None:
    """The procedure is ambient, not on demand.

    It is loaded by an `@import` from `CLAUDE.md` rather than being a skill,
    because a process consulted only when someone remembers to consult it is the
    exact failure this engine was built about.
    """
    claude = (TEMPLATES / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@.claude/operating-procedure.md" in claude


@pytest.mark.parametrize(
    "name", sorted(SCAFFOLD | {"agents", "tests"})
)
def test_every_scaffold_file_init_promises_actually_exists(name: str) -> None:
    assert (TEMPLATES / name).exists(), f"templates/{name} is missing"


def test_no_template_points_at_the_plugins_own_directories() -> None:
    """Templates land in the user's repo and must describe that repo.

    A scaffolded document telling someone to look in `hooks/` is pointing at a
    read-only plugin cache they will never find.
    """
    offenders = []
    for path in TEMPLATES.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if ".claude/hooks" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"templates still point at .claude/hooks: {offenders}"
