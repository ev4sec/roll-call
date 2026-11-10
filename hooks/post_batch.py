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

**What stays per-edit.** The consult router and the pattern scan remain on
`PostToolUse`: their message is about one file, and the router's exit code is
the enforcement guarantee this plugin is built on. Bandit is the one part of
the scan that runs here, once over the Python files the batch wrote, because
starting it costs more than everything else an edit pays for.

**Two lanes run side by side.** The suite and the artifact build share one
lane, in that order, because both execute the working tree. The dependency
audit and bandit share the other, because they only read. Each lane finishes
well inside this hook's time limit at the default budgets; run in a row,
their worst cases did not.

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
import security_scan

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


def tree_lane(paths: list[str], session_id: object) -> list[dict | None]:
    """The checks that execute the working tree: the suite, then the build.

    One after the other on purpose. A build can write metadata into the
    source tree, and a suite running over a tree that is being written to
    reports on neither state.
    """
    results: list[dict | None] = []

    # The suite is whole-tree, so it runs once per repository touched. A
    # worktree edit resolves to its own root, as the per-edit hook always did.
    by_repo: dict[str, list[str]] = {}
    for path in paths:
        if backend_tests.is_relevant(path):
            by_repo.setdefault(_engine.repo_for(path), []).append(path)
    for repo, group in by_repo.items():
        results.append(backend_tests.run_suite(repo, ", ".join(group), session_id))

    built: set[str] = set()
    for path in paths:
        repo = artifact_check.repo_if_triggered(path)
        if repo is not None and repo not in built:
            built.add(repo)
            results.append(artifact_check.check_repo(repo, path.rsplit("/", 1)[-1]))
    return results


def read_lane(paths: list[str], session_id: object) -> list[dict | None]:
    """The checks that only read: the dependency audit and bandit.

    A refused package is looked for in every manifest edited, because that
    check reads the file itself. The audit proper is about the repository,
    so a manifest and its lockfile edited together are audited once.
    """
    results: list[dict | None] = []
    audited: set[tuple[str, str | None]] = set()
    for path in paths:
        if not dependency_audit.is_manifest(path):
            continue
        blocked = dependency_audit.banned(path)
        if blocked:
            results.append(blocked)
            continue
        basename = path.rsplit("/", 1)[-1]
        key = (_engine.repo_for(path), dependency_audit.ecosystem(basename))
        if key in audited:
            continue
        audited.add(key)
        results.append(dependency_audit.audit(key[0], key[1], basename, session_id))

    results.append(security_scan.bandit_batch(paths))
    return results


def _guarded(lane, name: str, paths: list[str], session_id: object) -> list[dict | None]:
    """A lane that fails says so instead of taking the other lane's report."""
    try:
        return lane(paths, session_id)
    except Exception as exc:
        return [{"systemMessage": f"{_engine.name()}: the {name} checks could not run ({exc})."}]


def run(payload: dict) -> dict | None:
    paths = edited_paths(payload)
    if not paths:
        return None
    session_id = payload.get("session_id")

    # Two lanes side by side. Run in a row, a slow suite, a slow audit, and a
    # slow build add up to more than this hook's own time limit, and a hook
    # killed at its limit reports nothing at all. The config is read before
    # the lanes start so neither reads it mid-parse.
    _engine.load()
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        tree = pool.submit(_guarded, tree_lane, "test and build", paths, session_id)
        read = pool.submit(_guarded, read_lane, "audit and scan", paths, session_id)
        results = tree.result() + read.result()

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
