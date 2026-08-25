#!/usr/bin/env python
"""SessionStart hook: tell a new project that roll-call is installed but asleep.

**The gap this closes.** The plugin installs once, at user scope, so it is live
in every repository the user opens. But the thing that makes it work,
`/roll-call:init`, is per project, and until it runs there is no `engine.toml`,
no routing table, and no agents on disk. A user who installs the plugin and
starts working gets a half-state where hooks fire against a project that has
never been described to them, and nothing anywhere says why.

Before this hook, the only thing that told anyone to run init was the README.
An onboarding step that depends on someone having read the documentation
carefully is the assumption this whole engine exists to stop making.

**Why it speaks once per project and then never again.** The plugin is active in
every repository, and most of them are not projects the user wants an engine in.
A hook that asks every session, in every repo, is the alarm that cries wolf, and
this project has written down more than once that such an alarm is worse than
none: it gets muted, and it takes the credible alarms down with it.

So the offer is made a single time per project directory and recorded under
`CLAUDE_PLUGIN_DATA`, which survives plugin updates. Declining is silence. There
is nothing to dismiss and nothing to configure.

**Three states, three behaviors.**

  set up and whole   silence. The operating procedure is already loaded into
                     the session by `CLAUDE.md`, so there is nothing this hook
                     can add that the session does not already know.
  set up and broken  say so every session. A missing routing table after
                     `engine.toml` exists is not a user who has not started, it
                     is a user whose setup is damaged, and that is worth
                     repeating until `/roll-call:doctor` is run.
  not set up         offer init, once, then never again.

Opt out permanently for a repository with an empty `.claude/.roll-call-ignore`.

Never blocks, always exits 0.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

CONFIG = ".claude/engine.toml"
ROUTING = ".claude/routing.toml"
AGENTS = ".claude/agents"
IGNORE = ".claude/.roll-call-ignore"


def project_dir() -> Path:
    """The repository root.

    `CLAUDE_PROJECT_DIR` is set by the harness. Unlike the other hooks there is
    no useful fallback here: this file lives in the plugin cache, so walking up
    from `__file__` finds the plugin, never the project. Absent the variable the
    honest answer is to say nothing.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path()


def already_offered(project: Path) -> bool:
    """Have we made the offer for this directory before?

    Keyed by a hash of the resolved path rather than the path itself, so the
    record does not become a readable list of every repository on the machine.
    """
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data:
        # No durable store. Speak anyway: being told twice is a smaller failure
        # than never being told, and `.roll-call-ignore` is the escape hatch.
        return False
    digest = hashlib.sha256(str(project.resolve()).encode("utf-8"))
    key = digest.hexdigest()[:16]
    stamp = Path(data) / "offered" / key
    if stamp.exists():
        return True
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
    except OSError:
        pass
    return False


def say(message: str) -> int:
    json.dump({"systemMessage": message}, sys.stdout)
    return 0


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    project = project_dir()
    if not os.environ.get("CLAUDE_PROJECT_DIR"):
        return 0
    if (project / IGNORE).exists():
        return 0

    if not (project / CONFIG).exists():
        if already_offered(project):
            return 0
        return say(
            "roll-call is installed but not set up in this project. "
            "Run /roll-call:init to describe the repository to the engine and "
            "write the roster into .claude/. Nothing happens until you do. "
            "To silence this here, create .claude/.roll-call-ignore."
        )

    expected = ((ROUTING, project / ROUTING), (AGENTS, project / AGENTS))
    missing = [name for name, path in expected if not path.exists()]
    if missing:
        # Plural agreement matters here: this text is read by a person who is
        # already confused about why their setup is half-built.
        verb = "is" if len(missing) == 1 else "are"
        return say(
            "roll-call is configured here but incomplete: "
            + ", ".join(missing)
            + f" {verb} missing. The consult router cannot route without it. "
            "Run /roll-call:doctor."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
