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

The root `CLAUDE.md` is deliberately not compared. Init appends a marked
section to an existing file rather than owning it, so a diff against the
template would report the user's own constitution as drift, which is noise
wearing a finding's name.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scaffold  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"


def _project_facts(project: Path) -> SimpleNamespace:
    """The values init substituted, reconstructed from the instantiated config.

    A missing or unreadable engine.toml degrades to the template's own
    placeholder values, which makes the substitution a no-op and the comparison
    a raw diff: correct for a repo where init never filled anything in.
    """
    name, slug, source_root = "PROJECT_NAME", "project_slug", "src/project_slug"
    config = project / ".claude" / "engine.toml"
    try:
        import tomllib
        with config.open("rb") as fh:
            section = tomllib.load(fh).get("project", {})
        name = str(section.get("name", name))
        slug = str(section.get("slug", slug))
        source_root = str(section.get("source_root", source_root))
    except (OSError, Exception):  # noqa: BLE001 - degrade to raw comparison
        pass
    return SimpleNamespace(project_name=name, slug=slug, source_root=source_root)


def _expected(template: Path, subs: dict[str, str]) -> list[str]:
    text, _ = scaffold.split_notes(scaffold.render(template, subs))
    return text.splitlines()


def _pairs(project: Path, test_dir: str) -> list[tuple[Path, Path]]:
    claude = project / ".claude"
    pairs = [(TEMPLATES / name, claude / name) for name in scaffold.DOCUMENTS]
    pairs += [(t, claude / "agents" / t.name)
              for t in sorted((TEMPLATES / "agents").glob("*.md"))]
    pairs += [(t, project / test_dir / t.name)
              for t in sorted((TEMPLATES / "tests").glob("*.py"))]
    repro = TEMPLATES / "repro" / "README.md"
    if repro.is_file():
        pairs.append((repro, claude / "repro" / "README.md"))
    return pairs


def _test_dir(project: Path) -> str:
    try:
        import tomllib
        with (project / ".claude" / "engine.toml").open("rb") as fh:
            return str(tomllib.load(fh).get("tests", {}).get("dir", "tests"))
    except (OSError, Exception):  # noqa: BLE001
        return "tests"


def report(project: Path) -> list[str]:
    subs = scaffold.substitutions(_project_facts(project))
    identical = 0
    lines: list[str] = []
    for template, local in _pairs(project, _test_dir(project)):
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
        lines.append(f"drifted: {rel} ({added} line(s) local-only, "
                     f"{removed} line(s) template-only)")
    lines.append(f"{identical} file(s) match the shipped templates.")
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
