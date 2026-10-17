#!/usr/bin/env python
"""PostToolBatch hook: run the expensive checks once per batch of edits.

**Why this exists.** The test suite, the dependency audit, and the artifact
build used to fire on `PostToolUse`, which runs once per tool call and runs
those calls' hooks concurrently. Four files edited in one parallel batch
started four full suite runs at the same moment, each reporting on a tree the
other three were still changing. `PostToolBatch` fires exactly once after
every tool call in a batch has resolved, with the whole batch in the payload,
so the suite runs once against the finished tree. A batch of one edit is still
a batch, so single edits are checked exactly as before.

**What stays per-edit.** The consult router and the security scan remain on
`PostToolUse`: their message is about one file, and the router's exit code is
the enforcement guarantee this plugin is built on. Nothing about them moves.

**How the results reach the session.** Each check returns the JSON it would
have printed as a PostToolUse hook. A `block` there is turned into context
here, with the same text: on this event a block stops the turn outright
instead of handing the failure to the model, and a test failure the model
never sees is a test failure nobody fixes. The context is injected before the
next model call, which is the same moment the per-edit block used to land.

**Paths come from `tool_input`.** The batch payload carries each call's
response serialized as text, not as the object the per-tool event provides,
so the edited path is read from the call's input, where it is always present.

Produces no output when no check has anything to say. Never blocks.
"""

from __future__ import annotations

import json
import sys

import _engine
import artifact_check
import backend_tests
import dependency_audit

EDIT_TOOLS = frozenset({"Write", "Edit", "NotebookEdit"})


def edited_paths(payload: dict) -> list[str]:
    """Every distinct path an editor tool wrote in this batch, in order."""
    seen: list[str] = []
    for call in payload.get("tool_calls") or []:
        if not isinstance(call, dict) or call.get("tool_name") not in EDIT_TOOLS:
            continue
        ti = call.get("tool_input") or {}
        if not isinstance(ti, dict):
            continue
        raw = ti.get("file_path") or ti.get("notebook_path")
        if isinstance(raw, str) and raw:
            path = raw.replace("\\", "/")
            if path not in seen:
                seen.append(path)
    return seen


def merge(results: list[dict | None]) -> dict | None:
    """One harness payload out of several checks' payloads, or None."""
    messages: list[str] = []
    context: list[str] = []
    for result in results:
        if not result:
            continue
        if result.get("decision") == "block" and result.get("reason"):
            context.append(str(result["reason"]))
        extra = result.get("hookSpecificOutput") or {}
        if isinstance(extra, dict) and extra.get("additionalContext"):
            context.append(str(extra["additionalContext"]))
        if result.get("systemMessage"):
            messages.append(str(result["systemMessage"]))
    if not messages and not context:
        return None
    out: dict = {}
    if messages:
        out["systemMessage"] = " ".join(messages)
    if context:
        out["hookSpecificOutput"] = {
            "hookEventName": "PostToolBatch",
            "additionalContext": "\n\n".join(context),
        }
    return out


def run(payload: dict) -> dict | None:
    paths = edited_paths(payload)
    if not paths:
        return None
    session_id = payload.get("session_id")
    results: list[dict | None] = []

    # The suite is whole-tree, so it runs once per repository touched. A
    # worktree edit resolves to its own root, as the per-edit hook always did.
    by_repo: dict[str, list[str]] = {}
    for path in paths:
        if backend_tests.is_relevant(path):
            by_repo.setdefault(backend_tests._engine.repo_for(path), []).append(path)
    for repo, group in by_repo.items():
        results.append(backend_tests.run_suite(repo, ", ".join(group), session_id))

    for path in paths:
        results.append(dependency_audit.check(path, session_id))

    built: set[str] = set()
    for path in paths:
        repo = artifact_check.repo_if_triggered(path)
        if repo is not None and repo not in built:
            built.add(repo)
            results.append(artifact_check.check_repo(repo, path.rsplit("/", 1)[-1]))

    return merge(results)


def main() -> int:
    if not _engine.initialized():
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    out = run(payload)
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
