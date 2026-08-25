#!/usr/bin/env python
"""PreToolUse hook: stop before anything leaves the machine.

Reads the tool-call JSON on stdin. If the command would *publish*: push to a
gated host, create a release or PR, or upload to a package registry. It returns
permissionDecision "ask" so the harness prompts before it runs. Anything else
produces no output.

**Scope: local commits are deliberately NOT guarded.** The control is over
publication, not over version control. A local commit is private and
reversible; gating it slows ordinary work and protects nothing.

**`git push` is gated by destination, not by the word "push".** An earlier
version asked on every push while labeling it "a push to GitHub", having never
looked at where the push was going. Wrong in both directions: it prompted for a
push to a local bare repo or an internal mirror, which publishes nothing, and
the label asserted a fact the hook had not checked. The remote is now resolved
to a URL and its host inspected against `[publish] gated_hosts`.

**Resolution failure still asks.** No such remote, no upstream, git unavailable,
an unparseable command line: all answer "ask", not "proceed". Narrowing a gate
must never turn an unknown into a pass, which is the same fail-closed reasoning
`main()` applies to a malformed payload.

**This hook can only stop the command. The brief is not automatable.** Whatever
the project requires alongside a publish: the usual shape is one or two
paragraphs on what is going out, its risk and reversibility, and what was
verified: is the session's job and belongs in the operating procedure.

Detection outside the push path stays deliberately over-broad, because a false
positive costs one confirmation prompt and a false negative is an unreviewed
publish.

Two measured parser bugs are fixed here and the fixes are worth preserving:
`git-push origin main` (the dashed builtin form) once ran unprompted, and
`git stash push -u`: a purely local operation: once prompted as a publish.
A false prompt on the local path is the worse of the two: it trains the habit of
approving without reading, on the one prompt that matters.
"""

import json
import os
import re
import shlex
import subprocess
import sys

import _engine

# Shell separators that start a new command: ; && || | & and newlines.
SEGMENT_SPLIT = re.compile(r"(?:\|\||&&|[;|&\n\r])")
CONTINUATION = re.compile(r"\\\r?\n")

# `git` / `gh` as bare words (not `mygit`, not `github`).
GIT_WORD = re.compile(r"(?<![\w./-])git(?:\.exe)?(?![\w.-])", re.IGNORECASE)
GH_WORD = re.compile(r"(?<![\w./-])gh(?:\.exe)?(?![\w.-])", re.IGNORECASE)

#: The dashed builtin form, `git-push origin main`. Checked on its own because
#: `GIT_WORD` deliberately refuses to match the `git` inside `git-push`: its
#: trailing lookahead rejects a following `-`.
GIT_DASHED_PUSH = re.compile(r"(?<![\w./-])git-push(?![\w.-])", re.IGNORECASE)

#: Global options accepted *before* a git subcommand that consume the next token.
#: `--opt=value` forms need no entry; they are one token and are skipped as flags.
GIT_GLOBAL_VALUE_FLAGS = frozenset(
    {"-C", "-c", "--exec-path", "--git-dir", "--work-tree", "--namespace", "--config-env"}
)

#: Subcommands whose *second* word being `push` still means a push to a remote.
#: `git subtree push --prefix=d origin gh-pages` genuinely publishes.
GIT_PUSH_SUBSUBCOMMANDS = frozenset({"subtree"})

# `gh` subcommands that write to GitHub, plus mutating REST calls. Not
# destination-checked: the `gh` CLI talks to GitHub by definition.
GH_PUBLISH = re.compile(
    r"(?<![\w-])(?:release|pr|repo|workflow|gist|secret)(?![\w-])[\s\S]*"
    r"(?<![\w-])(?:create|merge|edit|delete|sync|upload|run|set)(?![\w-])"
    r"|-X\s*(?:POST|PUT|PATCH|DELETE)",
    re.IGNORECASE,
)

#: Package publication across the common ecosystems. Strictly less reversible
#: than a push: a released version number can never be re-used.
PKG_PUBLISH = re.compile(
    r"(?<![\w-])(?:twine\s+upload"
    r"|(?:hatch|uv|flit|poetry)\s+publish"
    r"|python\s+-m\s+twine\s+upload"
    r"|npm\s+publish"
    r"|yarn\s+publish"
    r"|pnpm\s+publish"
    r"|cargo\s+publish"
    r"|gem\s+push"
    r"|docker\s+push)(?![\w-])",
    re.IGNORECASE,
)

#: `git push` flags that consume the *following* token, so that token is not the
#: remote. Booleans (`-u`, `--force`, `--tags`, ...) need no entry.
PUSH_VALUE_FLAGS = frozenset({"-o", "--push-option", "--receive-pack", "--exec", "--repo"})

#: Returned by `_named_target` when the command line cannot be parsed. A sentinel
#: rather than None, because None already means "no remote named, use the default"
#: and the two must lead to opposite outcomes.
UNPARSEABLE = "\x00unparseable"


def _host_of(url: str) -> str:
    """The hostname in a git remote URL, or "" for a local filesystem path.

    Handles the three forms git accepts: a real URL (`https://host/path`), the
    scp-like form (`git@host:path`), and a bare path. A Windows drive letter
    (`C:\\repo`) must read as a local path and not as a host called "c", which is
    why the bare scp-like branch requires a dot in the host.
    """
    text = url.strip().strip("'\"")
    if not text:
        return ""
    if "://" in text:
        authority = text.split("://", 1)[1].split("/", 1)[0]
        return authority.rsplit("@", 1)[-1].split(":", 1)[0].lower()
    if "@" in text and ":" in text.split("@", 1)[1]:
        return text.split("@", 1)[1].split(":", 1)[0].lower()
    if ":" in text:
        head = text.split(":", 1)[0]
        if "." in head:
            return head.lower()
    return ""


def _is_gated(url: str) -> bool:
    """Does this remote point at a host the project treats as publication?

    Substring rather than exact match: a self-hosted `github.acme.example` is
    still GitHub and still publication. Over-broad here costs one confirmation
    prompt; under-broad costs an unreviewed publish, which is the asymmetry this
    whole file is built around.
    """
    host = _host_of(url)
    if not host:
        return False
    return any(str(h).lower() in host for h in _engine.get("publish", "gated_hosts"))


def _git(args: list[str], cwd: str | None) -> str | None:
    """Run a read-only git command. None on any failure, which means "ask"."""
    try:
        done = subprocess.run(  # noqa: S603
            ["git", *args],
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def _named_target(tail: str) -> str | None:
    """The remote name or URL named in a `git push`, or None if implicit."""
    try:
        tokens = shlex.split(tail, posix=False)
    except ValueError:
        return UNPARSEABLE

    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            name = token.split("=", 1)[0]
            if name == "--repo":
                # `--repo=<url>` names the destination outright; `--repo <url>`
                # puts it in the next token, which the skip below picks up.
                if "=" in token:
                    return token.split("=", 1)[1]
                skip_next = False
                continue
            if name in PUSH_VALUE_FLAGS and "=" not in token:
                skip_next = True
            continue
        return token.strip("'\"")
    return None


def _push_url(tail: str, cwd: str | None) -> str | None:
    """The URL a `git push` would write to, or None if it cannot be determined."""
    target = _named_target(tail)
    if target == UNPARSEABLE:
        return None
    if target is None:
        # Bare `git push`: the upstream of the current branch, else `origin`.
        upstream = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd)
        target = upstream.split("/", 1)[0] if upstream and "/" in upstream else "origin"
    # Anything with a scheme, a `user@host:`, or a dotted host is already a URL.
    if _host_of(target):
        return target
    return _git(["remote", "get-url", target], cwd)


def push_tail(after_git: str) -> str | None:
    """The argument tail of a `git push`, or None if this git command is not one.

    **`push` must be the subcommand, not merely a word somewhere after `git`.**
    Searching for the word anywhere in the segment made `git stash push -u`
    prompt as a publish. Returns `""` for a bare `git push`, which is
    meaningful: no remote was named and the caller must resolve the upstream.
    """
    tokens = after_git.split()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("-"):
            break
        # `-C /tmp` and friends swallow the next token; `--git-dir=x` does not.
        if token in GIT_GLOBAL_VALUE_FLAGS:
            index += 1
        index += 1
    if index >= len(tokens):
        return None

    subcommand = tokens[index]
    if subcommand == "push":
        return " ".join(tokens[index + 1:])
    if subcommand in GIT_PUSH_SUBSUBCOMMANDS and "push" in tokens[index + 1:]:
        return " ".join(tokens[index + 1:])
    return None


def classify(cmd: str, cwd: str | None = None) -> str | None:
    """A human label for the publish action, or None if this does not publish."""
    registry = str(_engine.get("publish", "registry"))
    gate_push = bool(_engine.get("publish", "gate_git_push"))

    cmd = CONTINUATION.sub(" ", cmd)
    for segment in SEGMENT_SPLIT.split(cmd):
        # Also test a quote-stripped copy so `git pu''sh` is caught.
        for variant in (segment, segment.replace("'", "").replace('"', "")):
            if PKG_PUBLISH.search(variant):
                return f"a package upload to {registry}"
            dashed = GIT_DASHED_PUSH.search(variant)
            git = GIT_WORD.search(variant)
            tail = None
            if dashed:
                tail = variant[dashed.end():]
            elif git:
                tail = push_tail(variant[git.end():])
            if tail is not None and gate_push:
                url = _push_url(tail, cwd)
                if url is None:
                    return (
                        "a git push whose destination could not be resolved. Only "
                        "pushes to a gated host need review, but an unresolved "
                        "remote is treated as one rather than waved through"
                    )
                if _is_gated(url):
                    return f"a git push to a gated host ({_host_of(url)})"
                # A local mirror or ungated host publishes nothing. Keep
                # scanning: a later segment of the same command may still
                # publish, so this is a `continue` and never a `return None`.
                continue
            gh = GH_WORD.search(variant)
            if gh and GH_PUBLISH.search(variant, gh.end()):
                return "a write operation against GitHub via gh"
    return None


def ask(reason: str) -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def main() -> int:
    label = _engine.name()

    # Fail CLOSED. For a confirmation gate, unknown state must mean "ask", not
    # "proceed". An error that silently returned 0 would let a publish through
    # unprompted, which is the exact outcome the gate exists to prevent.
    try:
        data = json.load(sys.stdin)
        ti = data.get("tool_input") or {}
        cmd = ti.get("command") or ""
        cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    except Exception:
        return ask(
            f"{label} policy: could not parse the tool call to check whether it "
            f"publishes. Confirm this is safe to run."
        )

    if not isinstance(cmd, str):
        return ask(f"{label} policy: unrecognized command shape; confirm before running.")
    if not cmd.strip():
        return 0

    what = classify(cmd, cwd if isinstance(cwd, str) else None)
    if what:
        return ask(
            f"{label} policy: this looks like {what}. Publication needs the "
            f"maintainer's go-ahead, and a short review brief should accompany "
            f"it: what is going out and why, its risk and reversibility, and "
            f"what was verified. (Local commits are not gated, and neither are "
            f"pushes to ungated remotes.)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
