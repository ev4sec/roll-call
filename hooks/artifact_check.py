#!/usr/bin/env python
"""Build the distribution and inspect what is actually in it.

Wired through `post_batch.py`, which fires once after a batch of tool calls
has resolved; this file can also run on its own as a PostToolUse hook. When
packaging configuration changes, it builds the distribution into a temp
directory and asserts things about the real bytes:

  1. Nothing on the `forbidden` list is inside: the engine's own machinery
     (`.claude/`, `CLAUDE.md`), git internals, credential-shaped files, local
     databases.
  2. Everything on the `required_in_wheel` list is inside, where the project has
     files an install is broken without.

**This is the step most stacks are missing.** Every other hook, every agent, and
every test reads *source*. On the project this engine came from, the sdist was
found shipping the entire `.claude/` directory: every agent definition, every
hook, the vision and architecture documents, and four agents, three hooks and
ninety tests all missed it. `.git/info/exclude` kept those paths out of git, but
the build backend honors only `.gitignore`, where they never appeared. A
security review had reasoned it was defense-in-depth rather than a live leak.
One `python -m build` settled it.

**The generalization, which is the reusable part: when a claim is about what a
tool does, run the tool.** Reasoning about a build backend's documented
behavior is not evidence about this repository.

Blocking, deliberately: a leaked artifact is not always recoverable, and a
published version number can never be re-used.

Disable with `[artifact] enabled = false` for anything that is not a
distributable package. That is the right answer for an application, and a guard
that cannot apply should say nothing rather than nearly-fire.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

import _engine


def _compiled(section_key):
    out = []
    for entry in _engine.get("artifact", section_key):
        try:
            out.append(re.compile(str(entry)))
        except re.error as exc:
            print(f"artifact_check: bad pattern {entry!r} ({exc})", file=sys.stderr)
    return out


def build(repo, outdir):
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "build", "--outdir", outdir],
            capture_output=True, text=True, cwd=repo, timeout=300,
        )
    except FileNotFoundError:
        return None, "python -m build unavailable"
    except subprocess.TimeoutExpired:
        return None, "build timed out after 300s"
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-1500:]
        return None, "build FAILED:\n" + tail
    return outdir, None


def members(path):
    if path.endswith(".whl"):
        with zipfile.ZipFile(path) as z:
            return z.namelist()
    with tarfile.open(path) as t:
        # Strip the leading `pkg-version/` component from sdist entries.
        return [m.name.split("/", 1)[1] for m in t.getmembers()
                if m.isfile() and "/" in m.name]


def inspect(outdir):
    forbidden = _compiled("forbidden")
    required = _compiled("required_in_wheel")

    problems, checked = [], []
    for artifact in sorted(glob.glob(os.path.join(outdir, "*"))):
        name = os.path.basename(artifact)
        if not name.endswith((".whl", ".tar.gz")):
            continue
        try:
            names = members(artifact)
        except Exception as exc:
            problems.append(f"{name}: cannot read: {exc}")
            continue
        checked.append(f"{name} ({len(names)} files)")

        for entry in names:
            for rx in forbidden:
                if rx.search(entry):
                    problems.append(f"{name} SHIPS {entry}: matched {rx.pattern}")

        if name.endswith(".whl"):
            for rx in required:
                if not any(rx.search(e) for e in names):
                    problems.append(
                        f"{name} is MISSING a file matching {rx.pattern}: an "
                        f"install would be incomplete")
    return problems, checked


def repo_if_triggered(path: str) -> str | None:
    """The buildable repo this edit belongs to, or None if it is no trigger."""
    if not _engine.get("artifact", "enabled"):
        return None
    triggers = {str(t).lower() for t in _engine.get("artifact", "triggers")}
    if os.path.basename(path).lower() not in triggers:
        return None
    repo = _engine.repo_for(path)
    if not os.path.isfile(os.path.join(repo, "pyproject.toml")):
        return None
    try:
        import importlib.util
        if importlib.util.find_spec("build") is None:
            return None  # nothing to do until the build backend is installed
    except Exception:
        return None
    return repo


def check_repo(repo: str, edited: str) -> dict | None:
    """Build `repo` once and inspect the result. `edited` labels the report."""
    label = _engine.name()
    outdir = tempfile.mkdtemp(prefix=f"{_engine.slug()}-artifact-")
    try:
        built, err = build(repo, outdir)
        if err:
            return {
                "systemMessage": f"{label}: artifact build check could not run.",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "Artifact check: " + err,
                },
            }
        problems, checked = inspect(built)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    if problems:
        return {
            "decision": "block",
            "reason": (
                "Artifact check FAILED after editing " + edited
                + ":\n" + "\n".join("  " + p for p in problems)
                + "\n\nFix this with an allowlist in the build config "
                  "(only-include), not a denylist: a denylist regresses the "
                  "next time a file is added. Note that .git/info/exclude is "
                  "invisible to most build backends, which read only .gitignore."
            ),
            "systemMessage": f"{label}: built artifact contains {len(problems)} problem(s).",
        }
    if checked:
        return {"systemMessage": f"{label}: artifact check clean: " + ", ".join(checked)}
    return None


def check(path: str) -> dict | None:
    """The verdict for one edited path, or None when it is not a trigger."""
    repo = repo_if_triggered(path)
    if repo is None:
        return None
    return check_repo(repo, os.path.basename(path))


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

    out = check(path)
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
