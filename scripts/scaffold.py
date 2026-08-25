#!/usr/bin/env python
"""Copy the engine templates into a project, without ever destroying anything.

**Why this is a script and not prose in the command.** `/roll-call:init` has two
halves. Deciding what this repository is, which paths deserve a routing rule,
and how to describe the product is judgment, and belongs to the model. Copying
fifteen files, substituting placeholders, and refusing to clobber anything is
mechanical, and mechanical work done by a model is work done slightly
differently every time. The half that must be identical on every install is
here, where it can be tested.

**The rule that outranks every other rule in this file: nothing is
overwritten.** A user's existing `CLAUDE.md` is the record of decisions someone
made deliberately. An existing agent in `.claude/agents/` is a seat somebody
tuned. Replacing either is unrecoverable from the user's point of view, because
they did not ask for a merge and will not read a diff they did not expect. So:

  file absent     write it
  file present    skip it, and say so by name
  CLAUDE.md       append a marked section, never replace

The report distinguishes those three outcomes, because "wrote 15 files" and
"wrote 3 files and left 12 alone" mean very different things to whoever runs it.

**Placeholders come in two kinds and they are handled differently.**

  mechanical   `{{PROJECT}}`, `{{slug}}`, and friends. Filled from what the
               caller detected. Roughly 28 of the 50 slots.
  judgment     `{{WHO_THE_USER_IS_AND_WHAT_THEIR_SCARCE_RESOURCE_IS}}` and
               about twenty like it. **Left exactly as they are**, visible in
               the file, so `/roll-call:doctor` can count them and the user can
               see what the engine still does not know. Guessing these silently
               is how a document ends up authoritative and wrong.

Usage:
    python scaffold.py --project-name Acme --slug acme --source-root src/acme \\
        [--stack python] [--test-dir tests] [--dry-run] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"

#: Written to `.claude/`. Order is cosmetic; the report reads better grouped.
DOCUMENTS = (
    "engine.toml", "routing.toml", "operating-procedure.md", "agent-brief.md",
    "agent-findings.md", "slice.md", "vision.md", "roadmap.md",
    "architecture.md", "security-invariants.md", "LESSONS.md",
    "parked-roles.md",
)

MARKER_OPEN = "<!-- roll-call:begin -->"
MARKER_CLOSE = "<!-- roll-call:end -->"

#: Installer guidance embedded in the templates as HTML comments.
INSTANTIATION = re.compile(r"[ \t]*<!--\s*INSTANTIATION:.*?-->\n?", re.S)

NOTES_FILE = ".claude/TEMPLATE-NOTES.md"
NOTES_HEADER = """# Template notes

Guidance that shipped inside the engine templates, lifted out here when they
were written into this repository.

**Why it is in a separate file.** These notes tell you how to fill in and
maintain the documents under `.claude/`. They are useful to a person and dead
weight to an agent, and the documents they came from are read constantly:
`agent-brief.md` is opened by all nine seats on every round, and each agent
definition is loaded on every one of its invocations. Left inline the notes
would have been a permanent tax on all of it.

Nothing reads this file automatically. It is here when you want it.
"""


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    appended: list[str] = field(default_factory=list)
    notes: list = field(default_factory=list)
    judgment_slots: int = 0

    def as_dict(self) -> dict:
        return {
            "written": self.written,
            "skipped": self.skipped,
            "appended": self.appended,
            "notes_lifted": sum(len(n) for _, n in self.notes),
            "judgment_slots": self.judgment_slots,
        }


def substitutions(args: argparse.Namespace) -> dict[str, str]:
    """Only the slots we actually know. Everything else survives untouched.

    Order matters: `render()` applies these sequentially, so the longer and
    more specific forms go first. `src/project_slug` must become the detected
    source root before the bare slug substitution turns it into `src/<slug>`,
    which is a guess about the repo layout rather than a fact about it.
    """
    return {
        "{{PROJECT}}": args.project_name,
        "{{slug}}": args.slug,
        "{{PROJECT_SLUG}}": args.slug,
        "src/project_slug": args.source_root,
        "src/PROJECT_SLUG": args.source_root,
        "PROJECT_NAME": args.project_name,
        "PROJECT_SLUG": args.slug,
        "project_slug": args.slug,
    }


def count_judgment_slots(text: str) -> int:
    """Remaining `{{...}}` slots after mechanical substitution."""
    import re

    return len(re.findall(r"\{\{[^}]+\}\}", text))


def render(source: Path, subs: dict[str, str]) -> str:
    text = source.read_text(encoding="utf-8")
    for needle, value in subs.items():
        text = text.replace(needle, value)
    return text


def split_notes(text: str) -> tuple[str, list[str]]:
    """Separate the document from the installer guidance buried in it.

    Returns the text with the comment blocks removed, and the blocks. Nothing is
    discarded: the caller writes them to `TEMPLATE-NOTES.md` so a person can
    still read them without every agent paying for them on every consult.
    """
    notes = [m.group(0).strip() for m in INSTANTIATION.finditer(text)]
    return INSTANTIATION.sub("", text), notes


def place(source: Path, target: Path, subs: dict[str, str], report: Report,
          dry_run: bool) -> None:
    """Write one file, or skip it because the user already has one."""
    label = str(target)
    if target.exists():
        report.skipped.append(label)
        return
    text = render(source, subs)
    text, notes = split_notes(text)
    if notes:
        report.notes.append((label, notes))
    report.judgment_slots += count_judgment_slots(text)
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    report.written.append(label)


def place_constitution(project: Path, subs: dict[str, str], report: Report,
                       dry_run: bool) -> None:
    """`CLAUDE.md` is the one file that merges rather than skipping.

    Skipping it entirely would leave the operating procedure unimported and the
    engine inert, which looks like a working install and is not one. Replacing
    it would destroy the user's own constitution. So an existing file gets a
    clearly fenced section appended, which a person can move or delete on sight.
    """
    target = project / "CLAUDE.md"
    # Strip the installer guidance here too. This file is auto-loaded into
    # every session, so a comment left inline is the most expensive one in the
    # whole scaffold: it is read on every turn, forever, by everything.
    body, _ = split_notes(render(TEMPLATES / "CLAUDE.md", subs))

    if not target.exists():
        report.judgment_slots += count_judgment_slots(body)
        if not dry_run:
            target.write_text(body, encoding="utf-8")
        report.written.append(str(target))
        return

    existing = target.read_text(encoding="utf-8")
    # Either marker means this file already reaches the procedure: the fenced
    # section from a previous append, or the raw import from a CLAUDE.md this
    # script wrote itself on an earlier run. Without the second check, running
    # init twice appends a duplicate import to its own output.
    if MARKER_OPEN in existing or "@.claude/operating-procedure.md" in existing:
        report.skipped.append(str(target))
        return

    section = (
        f"\n\n{MARKER_OPEN}\n"
        "## Operating procedure\n\n"
        "This project uses the roll-call engine. The standing procedure, the\n"
        "routing table, and the agent roster live under `.claude/` and belong\n"
        "to this repository.\n\n"
        "@.claude/operating-procedure.md\n"
        f"{MARKER_CLOSE}\n"
    )
    if not dry_run:
        target.write_text(existing + section, encoding="utf-8")
    report.appended.append(str(target))


def scaffold(project: Path, args: argparse.Namespace) -> Report:
    report = Report()
    subs = substitutions(args)
    claude = project / ".claude"

    for name in DOCUMENTS:
        place(TEMPLATES / name, claude / name, subs, report, args.dry_run)

    for agent in sorted((TEMPLATES / "agents").glob("*.md")):
        place(agent, claude / "agents" / agent.name, subs, report, args.dry_run)

    test_dir = project / args.test_dir
    for test in sorted((TEMPLATES / "tests").glob("*.py")):
        place(test, test_dir / test.name, subs, report, args.dry_run)

    repro = TEMPLATES / "repro" / "README.md"
    if repro.is_file():
        place(repro, claude / "repro" / "README.md", subs, report, args.dry_run)

    body, _ = split_notes(render(TEMPLATES / "CLAUDE.md", subs))
    _, constitution_notes = split_notes(body)
    if constitution_notes:
        report.notes.append((str(project / "CLAUDE.md"), constitution_notes))

    place_constitution(project, subs, report, args.dry_run)
    write_notes(project, report, args.dry_run)
    return report


def write_notes(project: Path, report: Report, dry_run: bool) -> None:
    """Collect every lifted comment block into one file nothing auto-loads."""
    if not report.notes:
        return
    target = project / NOTES_FILE
    if target.exists():
        return
    chunks = [NOTES_HEADER]
    for label, blocks in report.notes:
        chunks.append(f"\n## {Path(label).name}\n")
        for block in blocks:
            body = block.removeprefix("<!--").removesuffix("-->").strip()
            body = body.removeprefix("INSTANTIATION:").strip()
            # A block arrives carrying the indentation of the comment it sat
            # in, which renders as a code block once it is out of context.
            head, _, rest = body.partition("\n")
            body = head + ("\n" + textwrap.dedent(rest) if rest else "")
            chunks.append(body + "\n")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(chunks), encoding="utf-8")
    report.written.append(str(target))


def human(report: Report) -> str:
    lines = []
    if report.written:
        lines.append(f"Wrote {len(report.written)} files.")
    if report.appended:
        lines.append(
            f"Appended a marked section to {len(report.appended)} existing file(s): "
            + ", ".join(report.appended)
        )
    if report.skipped:
        lines.append(
            f"Left {len(report.skipped)} existing file(s) untouched: "
            + ", ".join(report.skipped)
        )
    if report.notes:
        lines.append(
            f"Lifted {sum(len(n) for _, n in report.notes)} template note(s) into "
            f"{NOTES_FILE}, so agents do not read them on every consult."
        )
    if report.judgment_slots:
        lines.append(
            f"{report.judgment_slots} placeholder(s) still need your judgment. "
            "They are visible in the files. Run /roll-call:doctor to list them."
        )
    return "\n".join(lines) or "Nothing to do."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--source-root", default="src",
                        help="Where the product's own code lives, repo-relative.")
    parser.add_argument("--test-dir", default="tests")
    parser.add_argument("--target", default=None,
                        help="Repo root. Defaults to CLAUDE_PROJECT_DIR or cwd.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    import os

    root = args.target or os.environ.get("CLAUDE_PROJECT_DIR") or "."
    project = Path(root).resolve()
    if not project.is_dir():
        print(f"not a directory: {project}", file=sys.stderr)
        return 1
    if not TEMPLATES.is_dir():
        print(f"templates missing at {TEMPLATES}", file=sys.stderr)
        return 1

    report = scaffold(project, args)
    print(json.dumps(report.as_dict(), indent=2) if args.json else human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
