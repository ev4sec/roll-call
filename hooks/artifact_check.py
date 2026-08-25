#!/usr/bin/env python
"""PostToolUse hook: build the distribution and inspect what is actually in it.

Reads the tool-call JSON on stdin. When packaging configuration changes, builds
the distribution into a temp directory and asserts things about the real bytes:

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


def main() -> int:
    if not _engine.get("artifact", "enabled"):
        return 0

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    ti = data.get("tool_input") or {}
    tr = data.get("tool_response") or {}
    path = (tr.get("filePath") or ti.get("file_path") or "").replace("\\", "/")

    triggers = {str(t).lower() for t in _engine.get("artifact", "triggers")}
    if os.path.basename(path).lower() not in triggers:
        return 0

    label = _engine.name()
    repo = _engine.repo_for(path)
    if not os.path.isfile(os.path.join(repo, "pyproject.toml")):
        return 0

    try:
        import importlib.util
        if importlib.util.find_spec("build") is None:
            return 0  # nothing to do until the build backend is installed
    except Exception:
        return 0

    outdir = tempfile.mkdtemp(prefix=f"{_engine.slug()}-artifact-")
    try:
        built, err = build(repo, outdir)
        if err:
            print(json.dumps({
                "systemMessage": f"{label}: artifact build check could not run.",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "Artifact check: " + err,
                },
            }))
            return 0
        problems, checked = inspect(built)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    if problems:
        print(json.dumps({
            "decision": "block",
            "reason": (
                "Artifact check FAILED after editing " + os.path.basename(path)
                + ":\n" + "\n".join("  " + p for p in problems)
                + "\n\nFix this with an allowlist in the build config "
                  "(only-include), not a denylist: a denylist regresses the "
                  "next time a file is added. Note that .git/info/exclude is "
                  "invisible to most build backends, which read only .gitignore."
            ),
            "systemMessage": f"{label}: built artifact contains {len(problems)} problem(s).",
        }))
    elif checked:
        print(json.dumps({
            "systemMessage": f"{label}: artifact check clean: " + ", ".join(checked),
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
