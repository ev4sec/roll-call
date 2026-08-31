#!/usr/bin/env python
"""PostToolUse hook: route the change to the agent that owns it, and mean it.

Reads the edited file path from the tool payload, matches it against
`.claude/routing.toml`, and checks `.claude/.consults` for whether the owning
agent has actually run recently. A `required` rule with no fresh consult exits 2
so the message reaches the session as feedback rather than scrolling past.

**Why this exists.** A prose routing table in the operating procedure did not
work. On the project this engine came from, one session shipped a
format-version bump that moved DDL, split two modules, relicensed the project
and changed the agent roster itself, and consulted **zero agents**. Every one of
those changes was named in that prose table. The instruction was read at session
start and lost by the third edit.

This is that control, mechanized, for the same reason `unreviewed_agent_edits.py`
exists: an instruction that is broken the same week it is written is not a
control.

**What it deliberately does not do.** It does not block the edit: PostToolUse
runs after the write, and stopping the keystroke was never the point. It makes
the omission *visible and repeated*, which is the difference between a rule and
a wish. It also never claims an agent's answer; it only reports whether one was
asked.

**Firing discipline.** Only `required` rules block, only on matching paths, and
only when the ledger has no consult inside `fresh_hours`. Most edits match
nothing. An alarm that cries wolf is worse than no alarm.

**Fails OPEN**, unlike the publish guard, which fails closed. An unknown state
at a publish gate might publish; here it merely cannot advise, and wedging every
edit in the repository over a syntax error is the worse failure.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import sys
import time
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 and older
    # Every other hook in this plugin already guards this import. This one did
    # not, which meant the single most valuable guard in the engine was also the
    # one that crashed hardest on an old interpreter, and crashed silently as
    # far as the user was concerned. Degrade loudly instead.
    tomllib = None  # type: ignore[assignment]

ROUTING = ".claude/routing.toml"
LEDGER = ".claude/.consults"

#: Where per-session "full block already shown" stamps live, under the
#: harness-provided plugin data directory. Absent that directory or a
#: session_id, the router degrades to rendering the full block every time,
#: which is exactly today's behavior.
STATE_DIRNAME = "router-seen"
STATE_TTL_SECONDS = 48 * 3600

#: Fire-rate ledger, hook-written and hook-read only. One line per owed rule
#: per firing. `/roll-call:doctor` aggregates it through scripts/route_stats.py
#: to find rules that fire constantly and never get consulted, which is the
#: measured version of the "watch it fire for a week" rule the routing-rule
#: skill already states. Never read by the model, so its cost is zero tokens.
STATS = ".claude/.route-stats"
STATS_WINDOW_SECONDS = 30 * 24 * 3600

#: Edits that cannot change behavior and should never summon anyone.
IGNORED_SUFFIXES = (".md", ".txt", ".lock")


def _project() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def _relative(path: str, project: Path) -> str | None:
    """Repo-relative POSIX path, or None if the edit is outside the project."""
    try:
        return Path(path).resolve().relative_to(project.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def _matches(rel: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True
        # `src/pkg/net/**` should match `src/pkg/net/client.py`. fnmatch treats
        # `**` as a single `*`, which stops at no separator on POSIX paths, so
        # the prefix form is checked explicitly.
        if pattern.endswith("/**") and rel.startswith(pattern[:-2]):
            return True
    return False


def _fresh_consults(project: Path, window_hours: float) -> set[str]:
    """Agents that ran inside the freshness window, from the append-only ledger."""
    ledger = project / LEDGER
    if not ledger.is_file():
        return set()
    cutoff = time.time() - window_hours * 3600
    fresh: set[str] = set()
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            name, _, stamp = line.partition("\t")
            try:
                if float(stamp) >= cutoff:
                    fresh.add(name.strip())
            except ValueError:
                continue
    except OSError:
        return set()
    return fresh


def _load_rules(project: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    with (project / ROUTING).open("rb") as fh:
        data = tomllib.load(fh)
    return data.get("settings", {}), data.get("rule", [])


def owed(rel: str, project: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Rules matching this path with no fresh consult: (required, advised)."""
    settings, rules = _load_rules(project)
    window = float(settings.get("fresh_hours", 24))
    fresh = _fresh_consults(project, window)

    required: list[dict[str, object]] = []
    advised: list[dict[str, object]] = []
    for rule in rules:
        if not _matches(rel, list(rule.get("paths", []))):
            continue
        # A path claimed by a broad glob but owned by a narrower rule can be
        # carved out explicitly, so one edit does not summon two seats.
        if _matches(rel, list(rule.get("exclude", []))):
            continue
        missing = [a for a in rule.get("agents", []) if a not in fresh]
        if not missing:
            continue
        entry = dict(rule)
        entry["missing"] = missing
        (required if rule.get("level") == "required" else advised).append(entry)
    return required, advised


def render(rel: str, required: list[dict[str, object]], settings: dict[str, object]) -> str:
    names: list[str] = []
    for rule in required:
        names.extend(str(a) for a in rule["missing"])  # type: ignore[union-attr]
    unique = sorted(set(names))

    lines = [
        f"CONSULT OWED for {rel}: {', '.join(unique)}",
        "",
    ]
    for rule in required:
        lines.append(f"[{rule['id']}] -> {', '.join(str(a) for a in rule['missing'])}")
        lines.append(f"  why: {str(rule.get('why', '')).strip()}")
        lines.append(f"  ask: {str(rule.get('question', '')).strip()}")
        lines.append("")

    limit = int(settings.get("max_parallel", 4))
    if len(unique) > limit:
        lines.append(
            f"{len(unique)} agents owed at once, over the max_parallel of {limit}. "
            f"That means this change is too broad to route. Narrow it, or run a "
            f"deliberate full design round and say so."
        )
    else:
        lines.append(
            "Launch them in PARALLEL in one message, not serially. Ask for a "
            "recommendation stated as the thing to build, not a menu; a list of "
            "options is an incomplete answer (Prime directive). Then reproduce "
            "every load-bearing claim before acting on it."
        )
    lines.append(
        "If this consult is genuinely not needed: routine implementation inside "
        "an already-approved design: say so explicitly in your next message and "
        "carry on. Do not silently skip it."
    )
    return "\n".join(lines)


def render_short(rel: str, repeats: list[dict[str, object]]) -> str:
    """One line per repeat firing. The full block already rendered this session.

    Still names the owed agents and the rule ids, and points at the file where
    the full text lives, so a session whose context was compacted after the
    full block can recover it with one cheap read instead of guessing.
    """
    names = sorted({str(a) for rule in repeats for a in rule["missing"]})  # type: ignore[union-attr]
    ids = ", ".join(str(rule.get("id", "?")) for rule in repeats)
    return (
        f"CONSULT OWED for {rel}: {', '.join(names)} (rules: {ids}; full text "
        f"in .claude/routing.toml, shown earlier this session). Consult now, "
        f"or declare the skip explicitly. Do not silently skip it."
    )


def _state_file(project: Path, session_id: object) -> Path | None:
    """Stamp file for this (repository, session) pair, or None to fail open.

    Keyed the way session_start's offer stamp already is: a hash of the repo
    path, so the store is not a readable list of the machine's repositories.
    Rule ids live inside the file as JSON, never as filenames, because they are
    user-authored TOML strings.
    """
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir or not isinstance(session_id, str):
        return None
    safe_session = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64]
    if not safe_session:
        return None
    repo_hash = hashlib.sha256(str(project.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path(data_dir) / STATE_DIRNAME / f"{repo_hash}-{safe_session}.json"


def _seen_rules(state: Path | None) -> set[str]:
    if state is None or not state.is_file():
        return set()
    try:
        loaded = json.loads(state.read_text(encoding="utf-8"))
        return {str(item) for item in loaded} if isinstance(loaded, list) else set()
    except (OSError, ValueError):
        return set()


def _record_rules(state: Path | None, rule_ids: list[str]) -> None:
    if state is None:
        return
    try:
        state.parent.mkdir(parents=True, exist_ok=True)
        merged = _seen_rules(state) | set(rule_ids)
        state.write_text(json.dumps(sorted(merged)), encoding="utf-8")
        _prune_stale(state.parent)
    except OSError:
        pass


def _prune_stale(directory: Path) -> None:
    """Old sessions' stamps are inert; drop them so the store stays small."""
    cutoff = time.time() - STATE_TTL_SECONDS
    try:
        for stamp in directory.iterdir():
            try:
                if stamp.stat().st_mtime < cutoff:
                    stamp.unlink()
            except OSError:
                continue
    except OSError:
        pass


def _append_stats(project: Path, entries: list[tuple[str, str]]) -> None:
    """Record firings, pruning past the window in the same write.

    Rewrite-not-append is deliberate: the window keeps the file small, and a
    ledger nothing prunes eventually gets noticed and deleted by hand, taking
    its history with it.
    """
    if not entries:
        return
    try:
        path = project / STATS
        now = time.time()
        cutoff = now - STATS_WINDOW_SECONDS
        lines: list[str] = []
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                _, _, stamp = line.rpartition("\t")
                try:
                    if float(stamp) >= cutoff:
                        lines.append(line)
                except ValueError:
                    continue
        lines.extend(f"{rid}\t{kind}\t{now:.0f}" for rid, kind in entries)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    path = (payload.get("tool_input") or {}).get("file_path")
    if not isinstance(path, str) or path.endswith(IGNORED_SUFFIXES):
        return 0

    project = _project()
    rel = _relative(path, project)
    if rel is None:
        return 0

    if tomllib is None:
        print(
            "consult_router: needs Python 3.11+ to read routing.toml. "
            "Routing is NOT being enforced. Run /roll-call:doctor.",
            file=sys.stderr,
        )
        return 0

    try:
        settings, _ = _load_rules(project)
        required, advised = owed(rel, project)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"consult_router: routing table unreadable ({exc})", file=sys.stderr)
        return 0

    compact = str(settings.get("repeat_style", "compact")) == "compact"
    if settings.get("stats", True):
        _append_stats(
            project,
            [(str(r.get("id", "?")), "R") for r in required]
            + [(str(r.get("id", "?")), "A") for r in advised],
        )

    if required:
        # Repeat compression: the full why/question prose renders once per rule
        # per session; later firings still exit 2 with a one-line demand. Any
        # missing piece (no session_id, no plugin data dir, unreadable state,
        # repeat_style = "full") fails toward the full block: verbose, never
        # silent.
        state = None
        if compact:
            state = _state_file(project, payload.get("session_id"))
        seen = _seen_rules(state)
        repeats = [r for r in required if str(r.get("id", "?")) in seen]
        first_time = [r for r in required if str(r.get("id", "?")) not in seen]

        if state is not None and not first_time:
            print(render_short(rel, repeats), file=sys.stderr)
        elif state is not None and repeats:
            print(
                render(rel, first_time, settings) + "\n" + render_short(rel, repeats),
                file=sys.stderr,
            )
        else:
            print(render(rel, required, settings), file=sys.stderr)
        _record_rules(state, [str(r.get("id", "?")) for r in required])
        return 2

    if advised:
        # routing.toml has documented advised as "mentioned once" since 0.1.0;
        # the code had no once-flag and re-printed on every matching edit. The
        # same session stamp that compresses required repeats now makes the
        # documentation true, keyed separately so the two cannot collide.
        state = _state_file(project, payload.get("session_id")) if compact else None
        keys = [f"advised:{r.get('id', '?')}" for r in advised]
        if state is None or any(k not in _seen_rules(state) for k in keys):
            names = sorted({str(a) for r in advised for a in r["missing"]})  # type: ignore[union-attr]
            print(f"consult advised for {rel}: {', '.join(names)}", file=sys.stderr)
            _record_rules(state, keys)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
