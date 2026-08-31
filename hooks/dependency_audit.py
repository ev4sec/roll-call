#!/usr/bin/env python
"""PostToolUse hook: audit dependencies whenever a manifest changes.

Reads the tool-call JSON on stdin. When a dependency manifest is edited, runs
the available CVE scanner over the declared runtime dependencies and reports
anything known-vulnerable.

**Why this fires on manifest edits specifically.** Editing a manifest is the
highest-leverage supply-chain moment there is. It is the one place a single
line pulls in arbitrary code, and on the project this engine came from it was
the one place no hook fired for the first day. `pip-audit` was declared in the
dev extras and never installed, so nothing scanned anything, and the gap was
invisible. **Declared is not installed, and a green suite proves neither.**

**Two severities, and the split matters.** A CVE is advisory context: real
information, but it should not wedge unrelated work, and a fresh advisory in a
transitive dependency is not something the current edit caused. A **policy-
banned** package is blocking, because that is a constraint the project wrote
down, not a fact about the world that changed overnight.

Configure both lists in `.claude/engine.toml` under `[dependencies]`. `banned`
is empty by default: a guard asserting a constraint the project does not have is
how guards get switched off.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import _engine


def _banned_pattern():
    """Regex over the project's refused packages, or None if the list is empty."""
    banned = [str(b) for b in _engine.get("dependencies", "banned") if str(b).strip()]
    if not banned:
        return None
    alternation = "|".join(re.escape(b) for b in banned)
    return re.compile(rf"[\"']?({alternation})", re.IGNORECASE)


def runtime_deps(repo):
    """Declared runtime dependencies, or None if they cannot be read.

    Python `pyproject.toml` and Node `package.json` are both understood, because
    those are the two manifests this hook is most often pointed at. Extend here
    for another ecosystem rather than in `main()`.
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

    package_json = os.path.join(repo, "package.json")
    if os.path.isfile(package_json):
        try:
            with open(package_json, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            deps = data.get("dependencies") or {}
            return [f"{k}{v}" if str(v)[:1].isdigit() else k for k, v in deps.items()]
        except Exception:
            return None
    return None


def _module_available(name):
    try:
        import importlib.util
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def audit(deps):
    """Run the available auditor over `deps`. Returns (findings, ran)."""
    if not shutil.which("pip-audit") and not _module_available("pip_audit"):
        return (["pip-audit is not installed: dependency CVEs are UNCHECKED. "
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


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    ti = data.get("tool_input") or {}
    tr = data.get("tool_response") or {}
    path = (tr.get("filePath") or ti.get("file_path") or "").replace("\\", "/")

    manifests = {str(m).lower() for m in _engine.get("dependencies", "manifests")}
    if os.path.basename(path).lower() not in manifests:
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

    deps = runtime_deps(repo)
    if deps is None:
        return 0

    findings, ran = audit(deps)
    if not findings:
        if ran:
            print(json.dumps({
                "systemMessage": f"{label}: {len(deps)} runtime deps audited, no known CVEs.",
            }))
        return 0

    # The missing-auditor nag repeats identically on every manifest edit until
    # pip-audit is installed. Teach once per session in full, then collapse to
    # one line that still says the CVEs are unchecked: collapsed, not silenced,
    # because "still unchecked" must never look like "audited and clean".
    if (not ran and findings[0].startswith("pip-audit is not installed")
            and not _engine.session_once(data.get("session_id"), "pip-audit-missing")):
        findings = ["pip-audit still not installed (full advisory earlier this "
                    "session); dependency CVEs remain UNCHECKED."]

    print(json.dumps({
        "systemMessage": f"{label}: dependency audit flagged {len(findings)} item(s).",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "Dependency audit after editing " + os.path.basename(path) + ":\n"
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
