#!/usr/bin/env python
"""Compare a repository's engine documents against the shipped templates.

**Why this is a script and not a procedure in the doctor command.** The old
procedure said "compare `.claude/` against the plugin templates" and left the
mechanics to the model, which on a full install means reading both sides of
roughly 16,500 words of templates: a 30k+ word bill landing on exactly the
sessions already in trouble. A diff is mechanical work, and mechanical work
done by a model is work done slightly differently every time, at a token price
per run. Here it can be tested, and the doctor command reports the lines.

**What makes this more than `diff -r`.** Init substituted the project's name,
slug and source root into every template and lifted the INSTANTIATION comments
out into TEMPLATE-NOTES.md. A naive diff reads all of that as drift. This
script re-applies the same substitutions (reconstructed from
`.claude/engine.toml`) and the same note-stripping before comparing, so what
remains is real divergence: a template that moved ahead, or a local file the
user tuned.

**What is deliberately NOT compared, because a difference there is the install
working rather than drift.** The root `CLAUDE.md`: init appends a marked
section rather than owning the file, so a diff would report the user's own
constitution as drift. `engine.toml` and `routing.toml`: init explicitly
mandates rewriting both to describe the project, so a healthy install diverges
from the template forever by design. And the living record documents (vision,
slice, roadmap, architecture, security-invariants, LESSONS, parked-roles,
agent-findings): their local content is the point of their existence, and a
permanent "drifted" line for every filled-in record would bury the one real
template drift when it arrives. What remains is the machinery prose the
plugin ships and improves: the operating procedure, the brief, the
measurement traps, the nine seats, the four project-side tests, and the repro
README.

Exit code is always 0. This is a report, not a gate. It never writes anything:
the local copy is the one the user tuned, and that is the whole reason it is
theirs.
"""

from __future__ import annotations

import argparse
import difflib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 and older
    tomllib = None  # type: ignore[assignment]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scaffold  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"


#: The machinery prose the plugin ships and improves; see the docstring for
#: why the config files and the living records are excluded.
MACHINERY = ("operating-procedure.md", "agent-brief.md", "measurement-traps.md")


def _engine_config(project: Path) -> tuple[SimpleNamespace | None, str, str | None]:
    """(substitution facts, test dir, error), from the instantiated config.

    A MISSING engine.toml degrades to the template's own placeholder values,
    which makes the substitution a no-op and the comparison a raw diff:
    correct for a repo where init never filled anything in. A PRESENT but
    unreadable engine.toml returns an error instead, because comparing with
    wrong substitutions would report every file as drifted while never naming
    the actual defect.
    """
    facts = SimpleNamespace(project_name="PROJECT_NAME", slug="project_slug",
                            source_root="src/project_slug", test_dir="tests")
    config = project / ".claude" / "engine.toml"
    if not config.is_file():
        return facts, facts.test_dir, None
    if tomllib is None:
        return None, facts.test_dir, "needs Python 3.11+ to read engine.toml"
    try:
        with config.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        return None, facts.test_dir, f"engine.toml unreadable ({exc})"
    except tomllib.TOMLDecodeError as exc:
        return None, facts.test_dir, f"engine.toml unparseable ({exc})"
    section = data.get("project", {})
    facts.project_name = str(section.get("name", facts.project_name))
    facts.slug = str(section.get("slug", facts.slug))
    facts.source_root = str(section.get("source_root", facts.source_root))
    facts.test_dir = str(data.get("tests", {}).get("dir", facts.test_dir))
    return facts, facts.test_dir, None


def _expected(template: Path, subs: dict[str, str]) -> list[str]:
    text, _ = scaffold.split_notes(scaffold.render(template, subs))
    return text.splitlines()


def _pairs(project: Path, test_dir: str) -> list[tuple[Path, Path]]:
    claude = project / ".claude"
    pairs = [(TEMPLATES / name, claude / name) for name in MACHINERY]
    pairs += [(t, claude / "agents" / t.name)
              for t in sorted((TEMPLATES / "agents").glob("*.md"))]
    pairs += [(t, project / test_dir / t.name)
              for t in sorted((TEMPLATES / "tests").glob("*.py"))]
    repro = TEMPLATES / "repro" / "README.md"
    if repro.is_file():
        pairs.append((repro, claude / "repro" / "README.md"))
    return pairs


def report(project: Path) -> list[str]:
    facts, test_dir, error = _engine_config(project)
    if error:
        return [f"drift: {error}. Comparing nothing, because wrong "
                f"substitutions would report every file as drifted while the "
                f"actual defect went unnamed. Fix .claude/engine.toml and "
                f"re-run."]
    subs = scaffold.substitutions(facts)
    identical = 0
    lines: list[str] = []
    for template, local in _pairs(project, test_dir):
        rel = local.relative_to(project).as_posix()
        if not local.is_file():
            lines.append(f"never installed: {rel} (shipped as templates/"
                         f"{template.relative_to(TEMPLATES).as_posix()})")
            continue
        expected = _expected(template, subs)
        actual = local.read_text(encoding="utf-8", errors="replace").splitlines()
        if expected == actual:
            identical += 1
            continue
        added = removed = 0
        for op in difflib.ndiff(expected, actual):
            if op.startswith("+ "):
                added += 1
            elif op.startswith("- "):
                removed += 1
        lines.append(f"differs: {rel} ({added} line(s) local-only, "
                     f"{removed} line(s) template-only)")
    lines.append(
        f"{identical} machinery file(s) match the shipped templates. Config "
        f"and record documents are yours and are not compared."
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=None,
                        help="Repo root. Defaults to CLAUDE_PROJECT_DIR or cwd.")
    args = parser.parse_args(argv)

    root = args.target or os.environ.get("CLAUDE_PROJECT_DIR") or "."
    project = Path(root).resolve()
    if not (project / ".claude").is_dir():
        print(f"drift: no .claude/ under {project}; is roll-call set up here?")
        return 0

    for line in report(project):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
