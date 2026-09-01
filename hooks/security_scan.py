#!/usr/bin/env python
"""PostToolUse hook: shift-left security scan of edited source.

Reads the tool-call JSON on stdin and scans the on-disk (post-edit) content of
the edited file against a check table chosen by file type.

**Two tables, and the split is the whole design.**

  * The **baseline** below is universal. Every check in it is wrong in almost
    every project, in almost every language that has the construct.
  * **Project checks live in `.claude/scan-rules.toml`** and are optional. That
    is where a project's own invariants go: the ones that make this hook worth
    more than a generic linter. Keep them there rather than editing this file,
    so the engine can be updated without losing them.

**Coverage is by extension, not by directory.** An earlier version returned
early on anything that was not a `.py` under the source root, which left the
HTML renderers (where XSS actually gets written), the data files (the untrusted
-input centerpiece), and the dependency manifests (the highest-leverage
supply-chain moment) entirely unscanned.

Findings at severity BLOCK return decision "block" so the failure is fed back
within the turn; WARN findings surface as context. Any single finding can be
suppressed with a trailing `<slug>: allow <check-id> - <reason>` comment on the
offending line, so every exception is deliberate and greppable.

If `bandit` is installed it runs on Python files as an additional WARN source.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tokenize

import _engine

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

BLOCK, WARN = "BLOCK", "WARN"

# Directories never worth scanning: vendored, generated, or local machinery.
# `.claude/` is excluded because this file's own patterns would match it.
SKIP_DIRS = ("/node_modules/", "/.venv/", "/venv/", "/dist/", "/build/",
             "/unpacked/", "/.git/", "/.claude/", "/__pycache__/", "/.ruff_cache/")

PROJECT_RULES = ".claude/scan-rules.toml"

# --- Baseline: Python --------------------------------------------------------
CHECKS_PY = [
    ("py-yaml-load", BLOCK,
     r"yaml\.(?:unsafe_)?load\s*\(|yaml\.load\s*\([^)]*Loader\s*=\s*(?:yaml\.)?(?:Full|Unsafe)Loader",
     "yaml.load on untrusted data is remote code execution. Use safe_load, and "
     "harden it further where the input comes from outside the project."),
    ("py-deserialize", BLOCK, r"\b(?:pickle|marshal)\.loads?\s*\(",
     "pickle/marshal deserialization is unsafe on any non-trusted data."),
    ("py-eval", BLOCK, r"(?<![\w.])(?:eval|exec)\s*\(",
     "eval()/exec(): arbitrary code execution risk."),
    ("py-shell", BLOCK, r"subprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True",
     "subprocess with shell=True: command-injection risk."),
    ("py-tls-off", BLOCK, r"verify\s*=\s*False",
     "TLS verification disabled. If a project genuinely needs this, it should be "
     "per-destination and explicit, never a global default."),
    ("py-secret-literal", BLOCK,
     r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*=\s*[\"'][^\"']{6,}[\"']",
     "possible hardcoded secret. Credentials belong in the OS keyring or the "
     "environment, never in source."),
    ("py-autoescape", BLOCK, r"autoescape\s*=\s*False",
     "template autoescaping disabled on content that may not be yours."),
    ("py-jinja-safe", BLOCK, r"\|\s*safe\b|(?<![\w.])Markup\s*\(",
     "|safe / Markup() bypasses autoescaping."),
    ("py-sql-fstring", BLOCK, r"(?:text|execute)\s*\(\s*f[\"']",
     "f-string SQL: use bound parameters."),
    ("py-debug", BLOCK, r"\bdebug\s*=\s*True",
     "debug=True leaks tracebacks, and tracebacks carry data and secrets."),
    ("py-cors", BLOCK, r"allow_origins\s*=\s*\[\s*[\"']\*[\"']",
     "wildcard CORS. On a loopback API this means any page the user visits can "
     "drive it."),
    ("py-extractall", BLOCK, r"\.extractall\s*\((?![^)]*filter\s*=)",
     "extractall without a filter: zip-slip / tar path traversal."),
    ("py-weak-hash", WARN, r"hashlib\.(?:md5|sha1)\b",
     "weak hash. Fine for a cache key, wrong for anything about integrity."),
    ("py-weak-random", WARN,
     r"(?<![\w.])random\.(?:random|randint|choice|choices|getrandbits|sample|shuffle)\s*\(",
     "use `secrets` for tokens, nonces and keys. `random` is predictable."),
    ("py-bind-all", WARN, r"[\"']0\.0\.0\.0[\"']",
     "binding all interfaces. Correct for a server, wrong for a local-only tool."),
    ("py-is-absolute", WARN, r"\.is_absolute\s*\(\s*\)",
     "is_absolute() is NOT a containment check on Windows: "
     "Path(r'\\Windows\\win.ini').is_absolute() is False yet resolves to "
     "C:\\Windows. Use resolve() + relative_to()."),
    ("py-dynamic-import", WARN, r"(?:importlib\.)?import_module\s*\(|\b__import__\s*\(",
     "dynamic import: a module chosen at runtime is invisible to import-graph "
     "checks. If the name can come from outside the project, resolve it through "
     "a pre-populated registry dict instead."),
]

# --- Baseline: frontend ------------------------------------------------------
CHECKS_WEB = [
    ("web-danger-html", BLOCK, r"dangerouslySetInnerHTML",
     "raw HTML sink in React. An XSS here is same-origin with whatever the page "
     "can reach."),
    ("web-inner-html", BLOCK,
     r"\.(?:innerHTML|outerHTML)\s*=|insertAdjacentHTML\s*\(|document\.write\s*\(",
     "raw HTML sink."),
    ("web-eval", BLOCK, r"(?<![\w.])eval\s*\(|new\s+Function\s*\(",
     "arbitrary code execution."),
    ("web-js-url", BLOCK, r"[\"']javascript:",
     "javascript: URL. Any user-supplied link field is exactly this vector: "
     "allowlist the scheme at the boundary."),
    ("web-sandbox-escape", BLOCK,
     r"sandbox\s*=\s*[\"'][^\"']*allow-scripts[^\"']*allow-same-origin",
     "allow-scripts + allow-same-origin together defeats the sandbox entirely."),
    ("web-dynamic-href", WARN, r"(?:href|src)\s*=\s*\{(?!\s*[\"'])",
     "computed href/src: React does not reliably block javascript: across "
     "versions. Use a scheme-allowlist helper."),
    ("web-srcdoc", WARN, r"srcdoc\s*=",
     "srcdoc renders untrusted markup; requires double-escaping to be safe."),
    ("web-blank-noopener", WARN,
     r"target\s*=\s*[\"']_blank[\"'](?![^>]*rel\s*=\s*[\"'][^\"']*noopener)",
     "target=_blank without rel=noopener: reverse tabnabbing."),
    ("web-markdown-html", WARN, r"html\s*:\s*true",
     "Markdown renderer with raw HTML enabled on content you did not write."),
]

BASELINE = {
    ".py": CHECKS_PY,
    ".ts": CHECKS_WEB, ".tsx": CHECKS_WEB, ".js": CHECKS_WEB,
    ".jsx": CHECKS_WEB, ".html": CHECKS_WEB, ".css": CHECKS_WEB,
}

COMMENT_PREFIXES = ("#", "//", "*", "/*", "<!--")

#: Checks that report as WARN rather than BLOCK inside a test file. A fixture
#: password or a debug flag in a test is the ordinary shape of a test, and a
#: block there would teach the reader to suppress the scan rather than read
#: it. The same line in product code still blocks.
TEST_RELAXED = frozenset({"py-secret-literal", "py-debug"})


def project_checks(suffix):
    """Project-specific checks for this extension, from `.claude/scan-rules.toml`.

    Schema, one table per check:

        [[check]]
        id       = "pack-anchor"
        severity = "BLOCK"          # or "WARN"
        suffixes = [".yaml", ".yml"]
        pattern  = "..."            # Python regex
        message  = "why this is wrong, and what to do instead"

    A malformed file is reported once and then ignored. Silence here would mean
    a project's own invariants stopped being enforced with no sign of it.
    """
    if tomllib is None:
        return []
    path = _engine.project_dir() / PROJECT_RULES
    if not path.is_file():
        return []
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"security_scan: {PROJECT_RULES} unreadable ({exc})", file=sys.stderr)
        return []

    out = []
    for check in data.get("check", []):
        try:
            if suffix not in [s.lower() for s in check["suffixes"]]:
                continue
            severity = BLOCK if str(check.get("severity", WARN)).upper() == BLOCK else WARN
            out.append((str(check["id"]), severity, str(check["pattern"]), str(check["message"])))
        except (KeyError, TypeError):
            print(f"security_scan: skipping malformed check in {PROJECT_RULES}", file=sys.stderr)
    return out


def mask_docstrings(lines):
    """Blank the body of triple-quoted strings, preserving line numbering.

    Docstrings routinely quote the very patterns these checks forbid: a module
    that explains why `eval` is banned trips the `eval` check by explaining it.
    A scanner that cannot tolerate documenting the pattern it forbids is one
    that gets suppressed everywhere, or switched off.

    Uses `tokenize` rather than a regex state machine. The regex version scanned
    for a triple quote anywhere on a line, so a `#` comment or an ordinary
    string that merely *mentioned* one opened a fake block and blinded the
    scanner to end of file: silently, reporting clean. **A false negative in
    the enforcement mechanism is far worse than the noise the masking removes.**

    Only triple-quoted strings are masked, not all literals: several checks
    (hardcoded secrets, "0.0.0.0", javascript: URLs) must see ordinary
    single-quoted literals to work at all.

    On unparseable source, returns the text unmasked: noisy, never blind.
    """
    src = "\n".join(lines)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError, ValueError):
        return list(lines)

    masked = list(lines)
    for tok in toks:
        if tok.type != tokenize.STRING:
            continue
        # Skip any string prefix (r, b, u, f and combinations) before checking.
        if not tok.string.lstrip("rbufRBUF").startswith(('"""', "'''")):
            continue
        (srow, scol), (erow, ecol) = tok.start, tok.end
        for row in range(srow, erow + 1):
            idx = row - 1
            if idx >= len(masked):
                break
            line = masked[idx]
            start = scol if row == srow else 0
            end = ecol if row == erow else len(line)
            masked[idx] = line[:start] + " " * max(0, end - start) + line[end:]
    return masked


def table_for(path):
    suffix = os.path.splitext(path)[1].lower()
    return BASELINE.get(suffix, []) + project_checks(suffix)


def scan_text(text, checks, is_python=False, relaxed=frozenset()):
    suppress = re.compile(rf"{re.escape(_engine.slug())}:\s*allow\s+([\w-]+)")
    compiled = []
    for cid, sev, rx, msg in checks:
        if cid in relaxed:
            sev = WARN
        try:
            compiled.append((cid, sev, re.compile(rx), msg))
        except re.error as exc:
            print(f"security_scan: bad pattern for {cid} ({exc})", file=sys.stderr)

    raw = text.splitlines()
    scanned = mask_docstrings(raw) if is_python else raw
    findings = []
    for lineno, (line, original) in enumerate(zip(scanned, raw), 1):
        if line.lstrip().startswith(COMMENT_PREFIXES):
            continue
        # Read suppressions off the original line: masking removes the comment.
        suppressed = set(suppress.findall(original))
        for cid, sev, rx, msg in compiled:
            if rx.search(line) and cid not in suppressed:
                findings.append((sev, cid, lineno, msg))
    return findings


def run_bandit(path, is_test=False):
    if not shutil.which("bandit"):
        return []
    cmd = ["bandit", "-q", "-f", "custom",
           "--msg-template", "L{line}: [{test_id}] {msg} ({severity})"]
    if is_test:
        # B101 is "assert used", which is what a test is. Without this, every
        # test file reports a wall of noise that trains you to ignore the
        # scanner.
        cmd += ["-s", "B101"]
    try:
        proc = subprocess.run(cmd + [path], capture_output=True, text=True, timeout=30)
        return [(WARN, "bandit", 0, ln.strip())
                for ln in (proc.stdout or "").splitlines() if ln.strip()]
    except Exception:
        return []


def main() -> int:
    if not _engine.initialized() or not _engine.get("scan", "enabled"):
        return 0

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    ti = data.get("tool_input") or {}
    tr = data.get("tool_response") or {}
    raw = tr.get("filePath") or ti.get("file_path") or ""
    path = raw.replace("\\", "/")

    if not path or not os.path.isfile(raw):
        return 0
    probe = "/" + path.strip("/") + "/"
    if any(skip in probe for skip in SKIP_DIRS):
        return 0

    checks = table_for(path)
    if not checks:
        return 0

    try:
        with open(raw, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except Exception:
        return 0

    is_py = path.endswith(".py")
    is_test = "/tests/" in path or os.path.basename(path).startswith("test_")
    findings = scan_text(
        text, checks, is_python=is_py, relaxed=TEST_RELAXED if is_test else frozenset(),
    )
    if is_py:
        findings += run_bandit(raw, is_test=is_test)

    if not findings:
        return 0

    label = _engine.name()
    blocking = [f for f in findings if f[0] == BLOCK]
    lines = ["  {} L{}: [{}] {}".format(sev, ln, cid, msg)
             for sev, cid, ln, msg in findings]
    detail = ("{} security scan on {}:\n{}\n"
              "Suppress a specific finding only with a deliberate trailing "
              "comment: `{}: allow <check-id> - <reason>`."
              .format(label, path, "\n".join(lines), _engine.slug()))

    name = os.path.basename(path)
    if blocking:
        print(json.dumps({
            "decision": "block",
            "reason": detail,
            "systemMessage": "{} security scan: {} blocking issue(s) in {}".format(
                label, len(blocking), name),
        }))
    else:
        print(json.dumps({
            "systemMessage": "{} security scan flagged {} item(s) in {}".format(
                label, len(findings), name),
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": detail,
            },
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
