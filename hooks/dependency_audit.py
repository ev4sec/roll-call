#!/usr/bin/env python
"""PostToolUse hook: audit dependencies whenever a manifest changes.

Reads the tool-call JSON on stdin. When a dependency manifest is edited, runs
the auditor for that manifest's ecosystem over the declared runtime
dependencies and reports anything known-vulnerable.

**Why this fires on manifest edits specifically.** Editing a manifest is the
highest-leverage supply-chain moment there is. It is the one place a single
line pulls in arbitrary code, and on the project this engine came from it was
the one place no hook fired for the first day. `pip-audit` was declared in the
dev extras and never installed, so nothing scanned anything, and the gap was
invisible. **Declared is not installed, and a green suite proves neither.**

**Two ecosystems, each with its own auditor.** A Python manifest
(`pyproject.toml`, `requirements.txt`, and their lockfiles) goes to
`pip-audit`. A Node manifest (`package.json` and its lockfiles) goes to
`npm audit`, which needs a lockfile to work from. When the auditor for an
ecosystem is unavailable the hook says so, because "unchecked" must never
read as "clean".

**Two severities, and the split matters.** A CVE is advisory context: real
information, but it should not wedge unrelated work, and a fresh advisory in a
transitive dependency is not something the current edit caused. A **policy-
banned** package is blocking, because that is a constraint the project wrote
down, not a fact about the world that changed overnight.

Configure both lists in `.claude/engine.toml` under `[dependencies]`. `banned`
is empty by default: a guard asserting a constraint the project does not have is
how guards get switched off. `enabled = false` turns the audit off entirely.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import _engine

PYTHON_MANIFESTS = {
    "pyproject.toml", "requirements.txt", "requirements-dev.txt", "uv.lock",
    "poetry.lock", "pipfile", "pipfile.lock",
}
NODE_MANIFESTS = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
    "pnpm-lock.yaml",
}
NODE_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json")

UNCHECKED = "dependency CVEs are UNCHECKED"


def ecosystem(basename):
    """Which auditor a manifest belongs to, or None for an unknown manifest."""
    name = basename.lower()
    if name in PYTHON_MANIFESTS:
        return "python"
    if name in NODE_MANIFESTS:
        return "node"
    return None


def _banned_pattern():
    """Regex over the project's refused packages, or None if the list is empty."""
    banned = [str(b) for b in _engine.get("dependencies", "banned") if str(b).strip()]
    if not banned:
        return None
    alternation = "|".join(re.escape(b) for b in banned)
    return re.compile(rf"[\"']?({alternation})", re.IGNORECASE)


def python_deps(repo):
    """Declared runtime dependencies, or None if they cannot be read.

    `pyproject.toml` is preferred; a bare `requirements.txt` is read as the
    fallback for projects that have not adopted one.
    """
    pyproject = os.path.join(repo, "pyproject.toml")
    if os.path.isfile(pyproject):
        try:
            import tomllib
            with open(pyproject, "rb") as fh:
                data = tomllib.load(fh)
            return data.get("project", {}).get("dependencies") or []
        except Exception:
            return None

    requirements = os.path.join(repo, "requirements.txt")
    if os.path.isfile(requirements):
        try:
            with open(requirements, "r", encoding="utf-8", errors="replace") as fh:
                lines = [ln.split("#", 1)[0].strip() for ln in fh]
            return [ln for ln in lines if ln and not ln.startswith("-")]
        except OSError:
            return None
    return None


def _module_available(name):
    try:
        import importlib.util
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def audit_python(deps):
    """Run pip-audit over `deps`. Returns (findings, ran)."""
    if not shutil.which("pip-audit") and not _module_available("pip_audit"):
        return ([f"pip-audit is not installed: {UNCHECKED}. "
                 "`pip install pip-audit`, and note that declaring it in the dev "
                 "extras is not the same as having it."],
                False)

    tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    try:
        tmp.write("\n".join(deps) + "\n")
        tmp.close()
        proc = subprocess.run(
            [sys.executable, "-m", "pip_audit", "-r", tmp.name,
             "--progress-spinner", "off"],
            capture_output=True, text=True, timeout=180,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            return ([], True)
        lines = [ln.rstrip() for ln in out.splitlines()
                 if ln.strip() and not ln.startswith("Found ")]
        return (lines[:25], True)
    except subprocess.TimeoutExpired:
        return (["pip-audit timed out (offline? it needs the advisory DB)"], False)
    except Exception as exc:
        return ([f"pip-audit could not run: {exc}"], False)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def audit_node(repo):
    """Run `npm audit` against the repository's lockfile. Returns (findings, ran)."""
    npm = shutil.which("npm")
    if npm is None:
        return ([f"npm is not on PATH: {UNCHECKED}."], False)
    if not any(os.path.isfile(os.path.join(repo, lock)) for lock in NODE_LOCKFILES):
        return ([f"no package-lock.json or npm-shrinkwrap.json: npm audit needs a "
                 f"lockfile, so {UNCHECKED}. `npm install --package-lock-only` "
                 f"writes one without installing anything."], False)
    try:
        proc = subprocess.run(
            [npm, "audit", "--omit=dev", "--json"],
            capture_output=True, text=True, cwd=repo, timeout=180,
        )
    except subprocess.TimeoutExpired:
        return (["npm audit timed out (offline? it needs the advisory service)"], False)
    except Exception as exc:
        return ([f"npm audit could not run: {exc}"], False)

    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        tail = [ln.rstrip() for ln in ((proc.stdout or "") + (proc.stderr or "")).splitlines()
                if ln.strip()]
        return (tail[-25:], proc.returncode == 0) if tail else ([], proc.returncode == 0)

    if "error" in data:
        summary = data["error"].get("summary") or str(data["error"])
        return ([f"npm audit could not run: {summary}"], False)

    findings = []
    for name, info in sorted((data.get("vulnerabilities") or {}).items()):
        severity = str(info.get("severity", "unknown"))
        via = [v.get("title") if isinstance(v, dict) else str(v) for v in info.get("via") or []]
        via = [v for v in via if v]
        detail = f" ({'; '.join(via[:2])})" if via else ""
        findings.append(f"{name}: {severity}{detail}")
    return (findings[:25], True)


def main() -> int:
    if not _engine.initialized() or not _engine.get("dependencies", "enabled"):
        return 0

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    ti = data.get("tool_input") or {}
    tr = data.get("tool_response") or {}
    path = (tr.get("filePath") or ti.get("file_path") or "").replace("\\", "/")

    manifests = {str(m).lower() for m in _engine.get("dependencies", "manifests")}
    basename = os.path.basename(path)
    if basename.lower() not in manifests:
        return 0

    label = _engine.name()
    repo = _engine.repo_for(path)

    # Blocking check first: a policy-banned package is a constraint violation.
    pattern = _banned_pattern()
    if pattern is not None and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            text = ""
        hit = pattern.search(text)
        if hit:
            print(json.dumps({
                "decision": "block",
                "reason": (
                    f"'{hit.group(1)}' is on this project's refused-dependency "
                    f"list. {_engine.get('dependencies', 'banned_reason')} "
                    f"Remove it, or bring the case to the maintainer. This is a "
                    f"recorded constraint, not a lint."
                ),
                "systemMessage": f"{label}: refused dependency blocked.",
            }))
            return 0

    eco = ecosystem(basename)
    if eco == "python":
        deps = python_deps(repo)
        if deps is None:
            return 0
        findings, ran = audit_python(deps)
        clean = f"{label}: {len(deps)} runtime deps audited, no known CVEs."
    elif eco == "node":
        findings, ran = audit_node(repo)
        clean = f"{label}: npm audit found no known CVEs in runtime deps."
    else:
        return 0

    if not findings:
        if ran:
            print(json.dumps({"systemMessage": clean}))
        return 0

    # An unavailable auditor repeats identically on every manifest edit until
    # it is installed. Teach once per session in full, then collapse to one
    # line that still says the CVEs are unchecked: collapsed, not silenced,
    # because "still unchecked" must never look like "audited and clean".
    if (not ran and UNCHECKED in findings[0]
            and not _engine.session_once(data.get("session_id"), "audit-unavailable")):
        findings = [f"dependency auditor still not installed (full advisory "
                    f"earlier this session); {UNCHECKED}."]

    print(json.dumps({
        "systemMessage": f"{label}: dependency audit flagged {len(findings)} item(s).",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "Dependency audit after editing " + basename + ":\n"
                + "\n".join("  " + f for f in findings)
                + "\nEvery dependency needs a stated reason in the same message "
                  "that adds it; a known-vulnerable one needs a version bump or "
                  "an explicit accepted-risk note."
            ),
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
