"""The plugin directory scans every version, and a held version waits for a
human reviewer before it can go live. These tests keep a change from adding a
new reason to hold it. They encode the checks as the directory states them
(claude.com/docs/plugins/pre-submission-checklist) and as its findings on
roll-call phrased them; see _working/LESSONS.md for the history.

They are a floor, not a model of the scanner: passing here does not promise a
clean scan, but failing here promises a finding.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: What a command or skill may pre-approve for the shell: an interpreter
#: spelling followed by one plugin script, named in full from the plugin root.
#: A bare interpreter, a `--version` probe, a relative path, or a wildcard
#: inside the path is held as broad shell access.
PINNED_SCRIPT = re.compile(
    r"^(?:python3|python|py -3) \$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w-]+\.py):\*$"
)

#: The only scoped write grant the commands need.
SCOPED_EDIT = "Edit(.claude/**)"

#: Tools that turn a command into a fetcher. None of the commands fetch.
NEVER_GRANTED = {"WebFetch", "WebSearch", "Write", "Edit", "Bash", "Bash(*)"}

#: Files that read the process environment today. Every one reads Claude
#: Code's own variables (CLAUDE_PROJECT_DIR and friends) or passes the
#: environment to a child process, and a reviewer has seen them. A new reader
#: raises "Uses a credential from the user's machine" for a fresh review, so
#: adding one should be a decision, made by editing this set.
ENVIRONMENT_READERS = {
    "hooks/_engine.py",
    "hooks/consult_router.py",
    "hooks/publish_guard.py",
    "hooks/session_start.py",
    "scripts/drift.py",
    "scripts/route_stats.py",
    "scripts/scaffold.py",
    "scripts/seat_stats.py",
    "scripts/validate.py",
    "templates/tests/test_consult_router.py",
    "tests/test_advisory_collapse.py",
    "tests/test_consult_router.py",
    "tests/test_repository_scope.py",
}

#: Package launchers and download commands block or hold a version. Spelled
#: in pieces so this file does not itself contain the strings it forbids.
LAUNCHERS = re.compile(
    r"\b(?:" + "|".join([
        "n" + "px", "bun" + "x", "uv" + "x", "pip" + "x run",
        "pnpm" + " dlx", "yarn" + " dlx", "uv" + " run",
        "cu" + "rl", "wg" + "et",
    ]) + r")\b"
)

SKIP_DIRS = {".git", "_working", ".playwright-mcp", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".sh", ".txt", ".ini", ""}


def shipped_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if SKIP_DIRS.intersection(rel.parts) or path.suffix not in TEXT_SUFFIXES:
            continue
        files.append(path)
    return files


def frontmatter_tools(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        return []
    line = re.search(r"^allowed-tools:\s*(.*)$", match.group(1), re.M)
    if not line:
        return []
    # Split on commas that sit outside parentheses.
    return [t.strip() for t in re.split(r",\s*(?![^()]*\))", line.group(1)) if t.strip()]


COMPONENTS = sorted(ROOT.glob("commands/*.md")) + sorted(ROOT.glob("skills/*/SKILL.md"))


@pytest.mark.parametrize("path", COMPONENTS, ids=lambda p: str(p.relative_to(ROOT)))
def test_shell_grants_are_pinned_to_an_existing_plugin_script(path: Path) -> None:
    for tool in frontmatter_tools(path):
        assert tool not in NEVER_GRANTED, f"{tool} is a broad grant"
        if tool.startswith("Bash("):
            inner = tool[len("Bash("):-1]
            match = PINNED_SCRIPT.match(inner)
            assert match, f"{tool} is not an interpreter pinned to a plugin script"
            assert (ROOT / "scripts" / match.group(1)).is_file(), f"{tool} names a missing script"
        elif tool.startswith(("Edit(", "Write(")):
            assert tool == SCOPED_EDIT, f"{tool} writes outside .claude/"


def test_no_new_file_reads_the_environment() -> None:
    # In pieces for the same reason as LAUNCHERS: this file must not look
    # like a reader to the scanner it is guarding against.
    markers = ("os." + "environ", "get" + "env")
    readers = set()
    for path in shipped_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(marker in text for marker in markers):
            readers.add(path.relative_to(ROOT).as_posix())
    added = readers - ENVIRONMENT_READERS
    assert not added, f"new environment readers will be reviewed again: {sorted(added)}"


def test_nothing_shipped_launches_or_downloads_a_package() -> None:
    hits = []
    for path in shipped_files():
        for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if LAUNCHERS.search(line):
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{number}: {line.strip()}")
    assert not hits, "\n".join(hits)
