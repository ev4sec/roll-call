#!/usr/bin/env python
"""PostToolUse hook: run the test suite after a relevant edit.

Reads the tool-call JSON on stdin. If the edited file can affect behavior, and
the test directory and runner both exist, it runs the suite. On failure it
returns decision "block" so the failure is fed back to the session to fix within
the turn. Otherwise it stays silent.

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

**This hook's cost becomes a design input, and that is worth planning for rather
than discovering.** It is what catches a wrong signature in the same turn it is
written, which is its whole value. But it runs the *whole* suite on every write,
so as the suite grows the price of a keystroke grows with it: measured on the
project this engine came from at two minutes for 1,534 tests and just over four
for 1,936, five days apart. Two consequences:

  * **A change that cannot compile until several files move together should be
    as few writes as possible.** Every intermediate edit otherwise triggers a
    full run whose only finding is "you are not finished yet."
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
import shutil
import subprocess
import sys

import _engine

#: Directories never worth triggering a suite for.
SKIP_DIRS = ("/node_modules/", "/.venv/", "/venv/", "/dist/", "/build/",
             "/unpacked/", "/.git/", "/.claude/", "/__pycache__/")

#: Extensions that can change behavior. Extend for the project's language.
CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb", ".java")


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

    if shutil.which(interpreter) is None:
        return None
    return [interpreter, *command]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    ti = data.get("tool_input") or {}
    tr = data.get("tool_response") or {}
    path = (tr.get("filePath") or ti.get("file_path") or "").replace("\\", "/")

    if not path or not is_relevant(path):
        return 0

    repo = _engine.repo_for(path)
    test_dir = str(_engine.get("tests", "dir"))
    if not os.path.isdir(os.path.join(repo, test_dir)):
        return 0

    command = build_command()
    if command is None:
        return 0  # test infra not installed yet: say nothing

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
        # Its own text names the failure mode ("trains the reader to scroll
        # past it"); this is that sentence, finally implemented.
        if _engine.session_once(data.get("session_id"), "tests-timeout"):
            print(json.dumps({
                "systemMessage": f"{label}: tests timed out after {timeout}s.",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"The test suite did not finish within {timeout}s. That is "
                        f"usually a hang -- an unbounded await, a pattern match with "
                        f"no input cap, or a real network call a socket-blocking "
                        f"fixture should have caught -- but it is equally the shape "
                        f"of a suite that has simply outgrown its budget. Run the "
                        f"suite yourself before acting on either reading. If it "
                        f"merely got slower, raise `tests.timeout` in the engine "
                        f"config: a hook that reports a timeout on every edit trains "
                        f"the reader to scroll past it, which costs exactly the day "
                        f"it fires for a real reason."
                    ),
                },
            }))
        else:
            print(json.dumps({
                "systemMessage": f"{label}: tests timed out again ({timeout}s).",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"The test suite timed out again ({timeout}s; full advisory "
                        f"earlier this session). Not shown green since: a hang, or "
                        f"a budget the suite outgrew. Run the suite yourself, or "
                        f"raise `tests.timeout` in .claude/engine.toml."
                    ),
                },
            }))
        return 0
    except OSError as exc:
        print(json.dumps({
            "systemMessage": f"{label}: could not start the test runner ({exc})."
        }))
        return 0

    if proc.returncode != 0:
        out = ((proc.stdout or "") + (proc.stderr or ""))[-3000:]
        print(json.dumps({
            "decision": "block",
            "reason": "Tests FAILED after editing " + path + ":\n" + out,
            "systemMessage": f"{label}: tests failed - see agent context.",
        }))
    else:
        # A green run resolves whatever the timeout advisory was tracking, so
        # the next timeout is a new event that must teach in full again; the
        # collapsed line's "not shown green since" stays true by construction.
        _engine.session_clear(data.get("session_id"), "tests-timeout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
