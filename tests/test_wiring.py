"""Nothing enforced the wiring, which is the same gap the hooks exist to close.

`test_engine_hooks.py` proves each hook survives being run. It says nothing
about whether the hook is ever *invoked*, and a hook that is never invoked is
indistinguishable from a hook that does not exist. The whole engine is built on
the observation that a control which fails silently is worse than no control, so
the wiring gets the same treatment as everything else.

**The three ways this file has seen wiring go wrong**, in rough order of how
quietly they fail:

1. A hook is added to `hooks/` and never wired. Its guard is absent and the file
   sitting there implies otherwise.
2. A hook is renamed or removed and `hooks.json` still names it. The command
   fails per invocation, and because guards must never block, it fails quietly.
3. A command is hand-edited and drifts from the `run.sh` dispatch, going back to
   invoking `python` directly. That reintroduces exactly the portability bug
   `run.sh` was written to fix, on the machines least likely to be the author's.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIRING = ROOT / "hooks" / "hooks.json"
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"

#: Files in `hooks/` that are deliberately not hooks.
NOT_HOOKS = {"_engine.py"}

DISPATCH = re.compile(
    r'^sh "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/run\.sh" ([a-z_]+)$'
)


def wiring() -> dict:
    return json.loads(WIRING.read_text(encoding="utf-8"))


def commands() -> list[tuple[str, dict]]:
    """Every configured hook handler, as (event, handler)."""
    out = []
    for event, groups in wiring()["hooks"].items():
        for group in groups:
            for handler in group["hooks"]:
                out.append((event, handler))
    return out


def wired_names() -> set[str]:
    names = set()
    for _, handler in commands():
        match = DISPATCH.match(handler["command"])
        if match:
            names.add(match.group(1))
    return names


def on_disk() -> set[str]:
    return {
        p.stem
        for p in (ROOT / "hooks").glob("*.py")
        if p.name not in NOT_HOOKS
    }


def test_the_manifest_and_wiring_are_valid_json() -> None:
    assert json.loads(MANIFEST.read_text(encoding="utf-8"))["name"] == "roll-call"
    assert wiring()["hooks"]


def test_every_wired_hook_exists_on_disk() -> None:
    missing = sorted(wired_names() - on_disk())
    assert not missing, f"hooks.json names hooks that do not exist: {missing}"


def test_every_hook_on_disk_is_wired() -> None:
    """An unwired hook is a guard nobody is getting."""
    unwired = sorted(on_disk() - wired_names())
    assert not unwired, f"hooks exist but nothing invokes them: {unwired}"


def test_every_command_goes_through_the_interpreter_shim() -> None:
    """No hook may invoke `python` directly.

    `python` does not exist on most macOS and Linux machines. A command that
    bypasses `run.sh` works on the author's box and fails on the installer's.
    """
    for event, handler in commands():
        command = handler["command"]
        assert DISPATCH.match(command), f"{event}: not a run.sh dispatch: {command}"


def test_the_shim_exists_and_is_a_posix_script() -> None:
    shim = ROOT / "hooks" / "run.sh"
    assert shim.is_file()
    assert shim.read_text(encoding="utf-8").startswith("#!/bin/sh")


def test_every_handler_declares_a_timeout_and_a_status_message() -> None:
    """Both are user-visible.

    A hook with no status message spins with no explanation, and one with no
    timeout inherits a ten-minute default that would hang a session on a build
    that never returns.
    """
    for event, handler in commands():
        assert handler.get("timeout"), f"{event}: no timeout on {handler['command']}"
        assert handler.get("statusMessage"), f"{event}: no statusMessage"


def test_the_router_is_wired_to_writes_and_the_ledger_to_agents() -> None:
    """The two halves of the mechanism, asserted by name.

    If the router stops firing on writes, or the ledger stops recording agents,
    the engine still installs, still runs, and enforces nothing at all.
    """
    events = {}
    for event, groups in wiring()["hooks"].items():
        for group in groups:
            for handler in group["hooks"]:
                match = DISPATCH.match(handler["command"])
                if match:
                    events[match.group(1)] = (event, group.get("matcher", ""))

    assert events["consult_router"][0] == "PostToolUse"
    assert "Write" in events["consult_router"][1]
    assert "Edit" in events["consult_router"][1]
    assert events["agent_watch"] == ("PostToolUse", "Agent")
    assert events["publish_guard"][0] == "PreToolUse"
    assert events["session_start"][0] == "SessionStart"
