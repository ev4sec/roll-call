#!/usr/bin/env python
"""Shared configuration loader for the engine's hooks.

The hooks in this directory are portable. Everything that differs between
projects lives in `.claude/engine.toml`, and this module is the only thing that
reads it.

**Three rules this module exists to enforce.**

1. **A missing or broken config is never fatal.** Every getter falls back to a
   default. A hook that refuses to run because its config has a typo is worse
   than a hook running in its generic form, because the first failure is silent
   and the second is visible in what the hook says.
2. **The config is read once per process.** Hooks are short-lived, so a module
   -level cache is sufficient and avoids re-parsing on every helper call.
3. **`CLAUDE_PROJECT_DIR` is the root, and it is not always set.** When absent,
   the repo is resolved from this file's own location, three levels up. Both
   answers can be wrong inside a git worktree, which is why the test hook
   resolves its root from the *edited file* instead. See `repo_for()`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 and older
    tomllib = None  # type: ignore[assignment]

CONFIG_PATH = ".claude/engine.toml"

_DEFAULTS: dict[str, dict[str, Any]] = {
    "project": {
        "name": "this project",
        "slug": "project",
        "source_root": "src",
    },
    "tests": {
        "dir": "tests",
        "command": ["-m", "pytest", "-q", "tests"],
        "interpreter": "",
        "timeout": 280,
        "root_marker": "pyproject.toml",
    },
    "dependencies": {
        "manifests": [
            "pyproject.toml",
            "package.json",
            "requirements.txt",
            "package-lock.json",
            "uv.lock",
            "poetry.lock",
        ],
        "banned": [],
        "banned_reason": "This project's stated constraints refuse this dependency.",
    },
    "publish": {
        "gated_hosts": ["github"],
        "gate_git_push": True,
        "registry": "the package registry",
    },
    "artifact": {
        "enabled": False,
        "triggers": ["pyproject.toml", "manifest.in", ".gitignore"],
        "forbidden": [
            r"(^|/)\.claude/",
            r"(^|/)CLAUDE\.md$",
            r"(^|/)\.git/",
            r"(^|/)\.env",
            r"\.(db|sqlite3?)$",
            r"\.(key|pem|p12|pfx)$",
            r"(^|/)\.venv/",
        ],
        "required_in_wheel": [],
    },
    "scan": {"enabled": True},
}

_cache: dict[str, Any] | None = None


def project_dir() -> Path:
    """The repository root.

    `CLAUDE_PROJECT_DIR` is set by the harness and is the only correct answer.

    There used to be a fallback that walked three levels up from `__file__`,
    which was right when these hooks lived at `<project>/.claude/hooks/`. Now
    they ship inside a plugin and run from the plugin cache, so that walk lands
    somewhere inside the installed plugin and never near the user's repository.
    A hook that resolves the wrong root does not fail; it reads the wrong
    config, scans the wrong files, and reports confidently about a tree nobody
    asked about. That is worse than not running.

    So the fallback is gone. Absent the variable this returns the current
    directory, and callers that need certainty check `have_project_dir()`.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path()


def have_project_dir() -> bool:
    """Whether the harness told us where the repository is.

    A hook doing anything destructive, expensive, or path-sensitive should stop
    when this is False rather than guess.
    """
    return bool(os.environ.get("CLAUDE_PROJECT_DIR"))


def load() -> dict[str, Any]:
    """Parsed `engine.toml`, merged over the defaults. Never raises."""
    global _cache
    if _cache is not None:
        return _cache

    merged: dict[str, Any] = {k: dict(v) for k, v in _DEFAULTS.items()}
    path = project_dir() / CONFIG_PATH
    if tomllib is not None and path.is_file():
        try:
            with path.open("rb") as handle:
                raw = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            # Loud, not fatal. A hook running generically still helps; a hook
            # that dies takes its guard with it and says nothing.
            print(f"engine.toml unreadable ({exc}); using defaults", file=sys.stderr)
            raw = {}
        for section, values in raw.items():
            if isinstance(values, dict):
                merged.setdefault(section, {}).update(values)
    _cache = merged
    return merged


def get(section: str, key: str, default: Any = None) -> Any:
    """One config value, with the built-in default behind it."""
    conf = load()
    if default is None:
        default = _DEFAULTS.get(section, {}).get(key)
    return conf.get(section, {}).get(key, default)


def name() -> str:
    """Project name, used to label every message a hook prints."""
    return str(get("project", "name"))


def slug() -> str:
    """Short identifier, used for suppression comments and temp-dir prefixes."""
    return str(get("project", "slug"))


def repo_for(edited_path: str) -> str:
    """The tree that owns `edited_path`, found by walking up to the root marker.

    **Resolving the root from a hook's own location is wrong the moment the edit
    happens in a git worktree**: the hook runs the *main* tree's suite and
    reports green for code it never saw. That was measured on the project this
    engine came from: a fabricated worktree path returned exit 0 in two seconds
    against the wrong tree. An agent working in an isolated worktree turns that
    from a curiosity into a silent pass, so resolve from the edit.
    """
    marker = str(get("tests", "root_marker"))
    candidate = os.path.abspath(edited_path)
    if os.path.isfile(candidate):
        candidate = os.path.dirname(candidate)
    while True:
        if os.path.isfile(os.path.join(candidate, marker)):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            return str(project_dir())
        candidate = parent
