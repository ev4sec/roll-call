#!/usr/bin/env python
"""Run the test suite after a relevant edit.

Wired through `post_batch.py`, which fires once after a batch of tool calls
has resolved and runs the suite once for the whole batch. This file can also
run on its own as a PostToolUse hook for a single edit; the logic is the same.
If the edited file can affect behavior, and the test directory and runner both
exist, it runs the suite. On failure the output is fed back to the session to
fix within the turn. Otherwise it stays silent.

**Two properties worth keeping when adapting this.**

  * **The repo root is derived from the edited file, not from `os.getcwd()` and
    not from `__file__`.** The cwd is whatever the last tool call left behind.
    Resolving from this file's own location is wrong the moment an edit happens
    inside a git worktree: the hook runs the *main* tree's suite and reports
    green for code it never saw. Measured on the project this engine came from,
    a fabricated worktree path returned exit 0 in two seconds against the wrong
    tree.
  * **A timeout is reported as advice, never as a failure.** A hanging suite is
    a diagnosis problem, and blocking on it hides the diagnosis.

**One failure is reported as advice too: the unfilled refusals list.**
`tests/test_permanent_refusals.py` ships failing on purpose until its list is
filled in, so that a guard asserting nothing cannot pass vacuously. Left as a
block, that one deliberate failure turned every source edit after init into a
"Tests FAILED" stop until someone filled the list, which teaches the reader to
approve past blocks. So when that test is the only failure, the hook says so
once per session in full, then in one line, and does not block. Any other
failure alongside it blocks as before.

**This hook's cost becomes a design input, and that is worth planning for rather
than discovering.** It is what catches a wrong signature in the same turn it is
written, which is its whole value. But it runs the *whole* suite on every write,
so as the suite grows the price of a keystroke grows with it: measured on the
project this engine came from at two minutes for 1,534 tests and just over four
for 1,936, five days apart. Two consequences:

  * **A change that cannot compile until several files move together should be
    as few writes as possible.** Every intermediate edit otherwise triggers a
    full run whose only finding is "you are not finished yet." Edits made in
    one parallel batch share a single run.
  * **A large mechanical sweep is cheaper as one scripted patch than as many
    edits**, but only if the script refuses to write anything unless every
    replacement matched the count expected. A blanket substitution that silently
    matched nothing looks exactly like one that applied, which is the same trap
    as a mutation test whose mutation never landed. Assert, then write.

Degrades to a no-op until test infrastructure exists, so it is harmless in an
empty repository. Configure the runner in `.claude/engine.toml` under `[tests]`.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import _engine

#: Directories never worth triggering a suite for.
SKIP_DIRS = ("/node_modules/", "/.venv/", "/venv/", "/dist/", "/build/",
             "/unpacked/", "/.git/", "/.claude/", "/__pycache__/")

#: Extensions that can change behavior. Extend for the project's language.
CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb", ".java")

#: The one test that is red by design on a fresh install.
REFUSALS_TEST = "test_the_refusal_list_has_been_filled_in"
FAILED_LINE = re.compile(r"^(?:FAILED|ERROR) ", re.M)
FAILED_COUNT = re.compile(r"\b(\d+) failed\b")


def is_relevant(path: str) -> bool:
    """True if editing this file could change test outcomes."""
    probe = "/" + path.strip("/") + "/"
    if any(skip in probe for skip in SKIP_DIRS):
        return False

    source_root = str(_engine.get("project", "source_root")).strip("/")
    test_dir = str(_engine.get("tests", "dir")).strip("/")

    if path.endswith(CODE_SUFFIXES):
        return (
            f"/{source_root}/" in path
            or f"/{test_dir}/" in path
            or os.path.basename(path) == "conftest.py"
        )
    if path.endswith((".yaml", ".yml")):
        # Data files that the suite validates. Narrow this per project rather
        # than triggering on every YAML in the tree.
        return "/fixtures/" in path or f"/{test_dir}/" in path
    return os.path.basename(path).lower() == str(_engine.get("tests", "root_marker")).lower()


def build_command() -> list[str] | None:
    """Argv for the suite, or None if the runner is not installed."""
    command = [str(c) for c in _engine.get("tests", "command")]
    interpreter = str(_engine.get("tests", "interpreter") or "")

    if not interpreter:
        # Python module invocation: verify the module is importable first, so a
        # missing runner is silence rather than a confusing non-zero exit.
        if command[:1] == ["-m"] and len(command) > 1:
            if importlib.util.find_spec(command[1].split(".")[0]) is None:
                return None
            return [sys.executable, *command]
        # A command whose first entry is not a Python option names its own
        # executable: `["npm", "test"]` runs npm, not Python.
        if command and not command[0].startswith("-"):
            executable = shutil.which(command[0])
            if executable is None:
                return None
            return [executable, *command[1:]]
        return [sys.executable, *command]

    if shutil.which(interpreter) is None:
        return None
    return [interpreter, *command]


def only_unfilled_refusals(output: str) -> bool:
    """True when the suite is red for exactly one reason: the refusals list.

    Reads pytest's short summary: exactly one FAILED or ERROR line, naming the
    refusals test, and a summary line counting one failure. Any other shape
    is a real failure and blocks.
    """
    lines = FAILED_LINE.findall(output)
    if len(lines) != 1:
        return False
    failed = [ln for ln in output.splitlines() if FAILED_LINE.match(ln)]
    if len(failed) != 1 or REFUSALS_TEST not in failed[0]:
        return False
    count = FAILED_COUNT.search(output)
    return bool(count) and count.group(1) == "1"


def _advice(label: str, headline: str, context: str) -> dict:
    return {
        "systemMessage": headline,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        },
    }


def run_suite(repo: str, edited: str, session_id: object) -> dict | None:
    """Run the suite for `repo` once. The harness JSON to print, or None.

    `edited` is only used to label the report; the suite is whole-tree.
    """
    test_dir = str(_engine.get("tests", "dir"))
    if not os.path.isdir(os.path.join(repo, test_dir)):
        return None

    command = build_command()
    if command is None:
        return None  # test infra not installed yet: say nothing

    label = _engine.name()
    timeout = int(_engine.get("tests", "timeout"))

    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, cwd=repo, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # The full advisory teaches once per session. Repeats collapse to one
        # line rather than nothing, because this hook is silent on success and
        # a suppressed warning would make "still hanging" look like "clean".
        if _engine.session_once(session_id, "tests-timeout"):
            return _advice(
                label, f"{label}: tests timed out after {timeout}s.",
                f"The test suite did not finish within {timeout}s. That is "
                f"usually a hang -- an unbounded await, a pattern match with "
                f"no input cap, or a real network call a socket-blocking "
                f"fixture should have caught -- but it is equally the shape "
                f"of a suite that has simply outgrown its budget. Run the "
                f"suite yourself before acting on either reading. If it "
                f"merely got slower, raise `tests.timeout` in the engine "
                f"config: a hook that reports a timeout on every edit trains "
                f"the reader to scroll past it, which costs exactly the day "
                f"it fires for a real reason.",
            )
        return _advice(
            label, f"{label}: tests timed out again ({timeout}s).",
            f"The test suite timed out again ({timeout}s; full advisory "
            f"earlier this session). Not shown green since: a hang, or "
            f"a budget the suite outgrew. Run the suite yourself, or "
            f"raise `tests.timeout` in .claude/engine.toml.",
        )
    except OSError as exc:
        return {"systemMessage": f"{label}: could not start the test runner ({exc})."}

    if proc.returncode == 0:
        # A green run resolves whatever the timeout advisory was tracking, so
        # the next timeout is a new event that must teach in full again; the
        # collapsed line's "not shown green since" stays true by construction.
        _engine.session_clear(session_id, "tests-timeout")
        return None

    output = (proc.stdout or "") + (proc.stderr or "")
    if only_unfilled_refusals(output):
        if _engine.session_once(session_id, "refusals-unfilled"):
            return _advice(
                label, f"{label}: the suite is red only on the unfilled refusals list.",
                f"The suite is red for one reason: `{REFUSALS_TEST}` in "
                f"tests/test_permanent_refusals.py, which fails on purpose until "
                f"its REFUSALS list is filled in. Nothing else failed. Fill the "
                f"list with the project's permanent refusals, or delete that "
                f"file and the procedure text that promises it. This is "
                f"reported, not blocked; any other failure still blocks.",
            )
        return _advice(
            label, f"{label}: suite still red only on the unfilled refusals list.",
            "The suite is still red only on the unfilled refusals list (full "
            "advisory earlier this session). Nothing else failed.",
        )

    return {
        "decision": "block",
        "reason": "Tests FAILED after editing " + edited + ":\n" + output[-3000:],
        "systemMessage": f"{label}: tests failed - see agent context.",
    }


def check(path: str, session_id: object) -> dict | None:
    """The verdict for one edited path, or None when there is nothing to say."""
    if not path or not is_relevant(path):
        return None
    return run_suite(_engine.repo_for(path), path, session_id)


def main() -> int:
    if not _engine.initialized():
        return 0

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    ti = data.get("tool_input") or {}
    tr = data.get("tool_response") or {}
    if not isinstance(tr, dict):
        tr = {}
    path = (tr.get("filePath") or ti.get("file_path") or "").replace("\\", "/")

    out = check(path, data.get("session_id"))
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
