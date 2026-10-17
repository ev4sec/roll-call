#!/usr/bin/env python
"""The mechanical half of the doctor's checklist, as code.

**Why this is a script and not prose in the doctor command.** For four
releases the doctor command told the model to check, by hand, whether each
routing rule's globs matched a real file, whether every named seat existed,
how many placeholders were left, and whether the ledgers were being written.
Every one of those is a count or a glob match, and a count done by a model is
done slightly differently every time, at a token price per run. The plugin's
own docstrings make that argument about every other check; this file applies
it to the rest of the checklist.

Four reports, each printing only what is wrong or unknown:

  config         engine.toml parses, and points at paths that exist.
  rules          every rule matches a real file, names a seat that exists, is
                 not so broad it will be muted, and does not carve a hole.
  placeholders   the `{{...}}` slots still waiting for judgment, per file.
  ledgers        the hooks are writing, the queue is being emptied, and no
                 consult is credited to a name that is not a seat.

The rule checks import the router's own matcher, so "dead" here means dead
there: a rule this report says matches nothing is a rule the router would
never fire. Files are listed through git so ignored directories do not count;
without git the tree is walked with the usual directories skipped.

Exit code is always 0. This is a report, not a gate. It never writes.
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 and older
    tomllib = None  # type: ignore[assignment]

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "hooks"))
import consult_router  # noqa: E402
import seat_stats  # noqa: E402

#: Values init leaves in engine.toml when it was never filled in.
TEMPLATE_VALUES = {"name": "PROJECT_NAME", "slug": "project_slug"}
TEMPLATE_SOURCE_ROOT = "project_slug"
#: A rule matching at least this share of the tree, and at least this many
#: files, will fire on most edits and be muted.
OVERBROAD_SHARE = 0.25
OVERBROAD_MIN_FILES = 20
PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}")
#: Documents whose unfilled slots leave a seat ruling from a blank record.
SEAT_CRITICAL = (".claude/agents/", ".claude/vision.md")
STALE_CONSULT_DAYS = 14
WALK_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


def _git(project: Path, args: list[str]) -> str | None:
    try:
        done = subprocess.run(  # noqa: S603
            ["git", *args], cwd=str(project), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def tree_files(project: Path) -> list[str]:
    """Repo-relative POSIX paths of every file the routing table could see."""
    out = _git(project, ["ls-files", "--cached", "--others", "--exclude-standard"])
    if out is not None:
        return sorted({ln.strip().replace("\\", "/") for ln in out.splitlines() if ln.strip()})
    files: list[str] = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(project)
        if WALK_SKIP.intersection(rel.parts):
            continue
        files.append(rel.as_posix())
    return sorted(files)


def _load_toml(path: Path) -> tuple[dict | None, str | None]:
    if tomllib is None:
        return None, "needs Python 3.11+ to read it"
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh), None
    except OSError as exc:
        return None, f"unreadable ({exc})"
    except tomllib.TOMLDecodeError as exc:
        return None, f"does not parse ({exc})"


def test_dir(project: Path) -> str:
    data, _ = _load_toml(project / ".claude" / "engine.toml")
    if not data:
        return "tests"
    return str((data.get("tests") or {}).get("dir", "tests"))


# ------------------------------------------------------------------- config --

def config_report(project: Path) -> list[str]:
    config = project / ".claude" / "engine.toml"
    if not config.is_file():
        return ["engine.toml is missing; every hook is inert here. Run /roll-call:init."]
    data, error = _load_toml(config)
    if data is None:
        return [f"engine.toml {error}; every hook is running on its defaults."]

    lines: list[str] = []
    proj = data.get("project") or {}
    for key, template in TEMPLATE_VALUES.items():
        if proj.get(key) == template:
            lines.append(f"[project] {key} still carries the template's value {template!r}.")
    source_root = str(proj.get("source_root", "src"))
    if TEMPLATE_SOURCE_ROOT in source_root:
        lines.append(f"[project] source_root {source_root!r} is the template's guess, not this repository.")
    elif not (project / source_root).is_dir():
        lines.append(
            f"[project] source_root {source_root!r} is not a directory; the agent-edit "
            f"guard and the test trigger watch a path that does not exist."
        )

    tests = data.get("tests") or {}
    tdir = str(tests.get("dir", "tests"))
    if not (project / tdir).is_dir():
        lines.append(f"[tests] dir {tdir!r} does not exist; the test hook does nothing.")
    interpreter = str(tests.get("interpreter") or "")
    command = [str(c) for c in (tests.get("command") or [])]
    if interpreter and shutil.which(interpreter) is None:
        lines.append(f"[tests] interpreter {interpreter!r} is not on PATH; the suite never runs.")
    elif (not interpreter and command and not command[0].startswith("-")
          and shutil.which(command[0]) is None):
        lines.append(f"[tests] command {command[0]!r} is not on PATH; the suite never runs.")
    return lines or ["config: engine.toml parses and points at real paths."]


# -------------------------------------------------------------------- rules --

def _paths_match(rel: str, rule: dict) -> bool:
    """Mirrors the router's path gate: the suffix rule, then the globs."""
    paths = [str(p) for p in rule.get("paths", [])]
    if rel.lower().endswith(consult_router.IGNORED_SUFFIXES):
        return consult_router._literal(rel) in {consult_router._literal(p) for p in paths}
    return consult_router._matches(rel, paths)


def _excluded(rel: str, rule: dict) -> bool:
    return consult_router._matches(rel, [str(p) for p in rule.get("exclude", [])])


def _fires(rel: str, rule: dict) -> bool:
    return _paths_match(rel, rule) and not _excluded(rel, rule)


def rules_report(project: Path) -> list[str]:
    routing = project / ".claude" / "routing.toml"
    if not routing.is_file():
        return ["routing.toml is missing; nothing routes."]
    data, error = _load_toml(routing)
    if data is None:
        return [f"routing.toml {error}; the router is advising nothing."]
    rules = [r for r in data.get("rule", []) if isinstance(r, dict)]
    if not rules:
        return ["routing.toml has no rules; the router is advising nothing."]

    agents_dir = project / ".claude" / "agents"
    seats = {p.stem for p in agents_dir.glob("*.md")} if agents_dir.is_dir() else set()
    files = tree_files(project)
    lines: list[str] = []

    for rule in rules:
        rid = str(rule.get("id") or consult_router._rule_key(rule))
        for agent in rule.get("agents", []):
            if str(agent) not in seats:
                lines.append(
                    f"rule {rid}: names seat {agent!r}, which has no file in "
                    f".claude/agents/; a required consult there can never be satisfied."
                )
        hits = [f for f in files if _fires(f, rule)]
        if not hits:
            lines.append(f"rule {rid}: matches no file in the tree; it can never fire.")
        elif (len(hits) >= OVERBROAD_MIN_FILES
              and len(hits) / max(len(files), 1) >= OVERBROAD_SHARE):
            lines.append(
                f"rule {rid}: matches {len(hits)} of {len(files)} files. A rule that "
                f"fires on most edits gets muted and takes the credible rules with it."
            )
        carved = [f for f in files if _paths_match(f, rule) and _excluded(f, rule)]
        orphans = [
            f for f in carved
            if not any(other is not rule and _fires(f, other) for other in rules)
        ]
        if orphans:
            shown = ", ".join(orphans[:3])
            lines.append(
                f"rule {rid}: its exclude leaves {len(orphans)} file(s) covered by no "
                f"rule ({shown}); that is a hole, not a boundary."
            )

    named = {str(a) for r in rules for a in r.get("agents", [])}
    for seat in sorted(seats - named):
        lines.append(
            f"seat {seat}: no rule routes to it; a seat the mechanism never summons "
            f"is decoration."
        )
    required = sum(1 for r in rules if r.get("level") == "required")
    if required == 0:
        lines.append(
            f"posture: all {len(rules)} rule(s) are advised; the engine is advising "
            f"and enforcing nothing. Promote a rule once it has fired quietly for a week."
        )
    return lines or [
        f"rules: {len(rules)} rule(s), each matching real files and naming a seat that exists."
    ]


# ------------------------------------------------------------- placeholders --

def refusals_unfilled(path: Path) -> bool:
    """True when `REFUSALS` in the test file is still the empty list."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
            value = node.value
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        else:
            continue
        if "REFUSALS" in targets and isinstance(value, ast.List) and not value.elts:
            return True
    return False


def placeholders_report(project: Path) -> list[str]:
    tdir = test_dir(project)
    candidates: list[Path] = [project / "CLAUDE.md"]
    claude = project / ".claude"
    if claude.is_dir():
        candidates += sorted(claude.rglob("*.md"))
        candidates += sorted(claude.glob("*.toml"))
    tests = project / tdir
    if tests.is_dir():
        candidates += sorted(tests.glob("test_*.py"))

    counts: dict[str, int] = {}
    for path in candidates:
        if not path.is_file() or path.name == "TEMPLATE-NOTES.md":
            continue
        try:
            found = len(PLACEHOLDER.findall(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
        if found:
            counts[path.relative_to(project).as_posix()] = found

    lines: list[str] = []
    total = sum(counts.values())
    if total:
        lines.append(f"{total} placeholder(s) still need judgment, in {len(counts)} file(s):")
        for rel, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            tag = " (a seat rules from a blank record until filled)" if rel.startswith(SEAT_CRITICAL) else ""
            lines.append(f"  {rel}: {n}{tag}")
    refusals = tests / "test_permanent_refusals.py"
    if refusals.is_file() and refusals_unfilled(refusals):
        lines.append(
            f"{tdir}/test_permanent_refusals.py: REFUSALS is empty, so the suite is red "
            f"by design until it is filled; the test hook reports this and does not block."
        )
    return lines or ["placeholders: none left."]


# ------------------------------------------------------------------ ledgers --

def ledgers_report(project: Path, now: float | None = None) -> list[str]:
    now = time.time() if now is None else now
    claude = project / ".claude"
    lines: list[str] = []

    agents_dir = claude / "agents"
    seats = {p.stem for p in agents_dir.glob("*.md")} if agents_dir.is_dir() else set()

    consults = claude / ".consults"
    if not consults.is_file():
        lines.append(
            "no consult ledger yet: no seat has finished a run in this checkout. The "
            "router can only report that; it cannot cause a consult."
        )
    else:
        rows: list[tuple[str, float]] = []
        try:
            for line in consults.read_text(encoding="utf-8").splitlines():
                name, _, stamp = line.partition("\t")
                try:
                    rows.append((name.strip(), float(stamp)))
                except ValueError:
                    continue
        except OSError:
            rows = []
        if rows:
            age = (now - max(ts for _, ts in rows)) / 86400
            if age >= STALE_CONSULT_DAYS:
                lines.append(
                    f"the last consult was {age:.0f} days ago; the ledger holds "
                    f"{len(rows)} entries."
                )
            unnamed = sorted({name for name, _ in rows if name not in seats})
            if unnamed:
                count = sum(1 for name, _ in rows if name not in seats)
                lines.append(
                    f"{count} of {len(rows)} consult entries name no seat on the roster "
                    f"({', '.join(unnamed[:4])}); those runs credit no rule."
                )

    pending = claude / ".pending-findings"
    if pending.is_file():
        try:
            ignore = (claude / ".gitignore").read_text(encoding="utf-8")
        except OSError:
            ignore = ""
        if ".pending-findings" not in ignore:
            lines.append(
                ".claude/.gitignore does not list .pending-findings; the claim queue "
                "shows up as an untracked file until the line is added."
            )

    findings = claude / "agent-findings.md"
    if findings.is_file():
        try:
            rows_ = seat_stats.ledger_rows(findings.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            rows_ = []
        if not rows_:
            lines.append("agent-findings.md has no verdict rows yet; the roster has no track record.")

    if not (claude / "scan-rules.toml").is_file():
        lines.append("no .claude/scan-rules.toml: the security scan runs its generic baseline only. Optional.")
    if (claude / ".agent-ran").is_file():
        lines.append(
            "agent edits are waiting for the commit guard (.claude/.agent-ran); "
            "the diff has not been reviewed."
        )
    return lines or ["ledgers: consults recorded, claims judged, nothing stale."]


SECTIONS = (
    ("config", config_report),
    ("rules", rules_report),
    ("placeholders", placeholders_report),
    ("ledgers", ledgers_report),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", default=".", help="Repo root of the install being checked.")
    args = parser.parse_args(argv)
    project = Path(args.target).resolve()
    if not (project / ".claude").is_dir():
        print(f"health: no .claude/ under {project}; is roll-call set up here?")
        return 0
    for name, run in SECTIONS:
        print(f"[{name}]")
        for line in run(project):
            print(line)
        print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
