"""Shared helpers for the hook tests.

`hook_env` is the one place the test suite reads the process environment to
build a hook's environment. The directory scanner reads every shipped file,
tests included, and counts each new environment reader as a fresh review
item, so the tests share this helper rather than each reading the variables.
"""

from __future__ import annotations

import os
from pathlib import Path


def hook_env(project: Path, *, inherit_path: bool = False, **extra: str) -> dict[str, str]:
    """The environment a hook runs under in these tests.

    PATH is empty unless `inherit_path` is set, so a hook cannot find a tool
    the test did not mean to give it. On Windows the system root travels along,
    because the interpreter needs it to start at all.
    """
    env = {"CLAUDE_PROJECT_DIR": str(project),
           "PATH": os.environ.get("PATH", "") if inherit_path else ""}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    env.update(extra)
    return env
