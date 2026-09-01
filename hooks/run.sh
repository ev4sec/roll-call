#!/bin/sh
# Find a usable Python and run the named hook with it.
#
# Every hook in this plugin goes through here rather than being invoked as
# `python hooks/whatever.py` directly. The reason is that `python` is not a
# portable name. On most macOS and Linux machines the interpreter is `python3`
# and a bare `python` does not exist at all, so a plugin wired to `python` fails
# on install for a large share of the people who try it, and fails in the least
# helpful way: a traceback from a shell, with no indication that a plugin they
# just installed is the cause.
#
# Order of preference: python3, python, py -3. First one that reports 3.11 or
# newer wins. The version floor is real rather than cosmetic: the hooks read
# TOML with `tomllib`, which entered the standard library in 3.11.
#
# When nothing suitable is found this says so once per session per machine,
# in words, and exits 0. It must never block a tool call. A guard that cannot
# run should make its absence visible and then get out of the way, because a
# session wedged by its own tooling is a worse outcome than an unguarded edit.
#
# Usage: sh run.sh <hook-name> [args...]      e.g. sh run.sh consult_router

set -u

HOOK_DIR=$(dirname "$0")
HOOK_NAME=${1:-}
[ -n "$HOOK_NAME" ] || exit 0
shift

TARGET="$HOOK_DIR/$HOOK_NAME.py"
[ -f "$TARGET" ] || exit 0

VERSION_PROBE='import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'

for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "$VERSION_PROBE" >/dev/null 2>&1; then
            exec "$candidate" "$TARGET" "$@"
        fi
    fi
done

# Windows launcher, which selects an interpreter rather than being one.
if command -v py >/dev/null 2>&1; then
    if py -3 -c "$VERSION_PROBE" >/dev/null 2>&1; then
        exec py -3 "$TARGET" "$@"
    fi
fi

# One warning per session per machine, matching the per-session once-flags
# the Python hooks use: a fresh session gets told its guards are inactive,
# and within a session the message does not repeat five times per edit, which
# trains the reader to scroll past the one copy that matters. The payload on
# stdin carries the session id; no Python exists here by definition, so it is
# fished out with sed, and an unparsable payload degrades to a per-day stamp.
# Without CLAUDE_PLUGIN_DATA it degrades to warning on every invocation, the
# same direction session_start degrades. Stale stamps age out after two days.
if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    # Read stdin only when it is a pipe: on a terminal (the file's own
    # documented manual usage) cat would block forever, and this script must
    # never hang a tool call.
    SESSION=""
    if [ ! -t 0 ]; then
        SESSION=$(cat 2>/dev/null | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9_-]\{1,64\}\)".*/\1/p' | head -n 1)
    fi
    [ -n "$SESSION" ] || SESSION="day-$(date +%Y%m%d 2>/dev/null || echo unknown)"
    mkdir -p "$CLAUDE_PLUGIN_DATA" 2>/dev/null
    # The stamp is a directory created with mkdir because mkdir is atomic:
    # five hooks fire in parallel on one edit, and check-then-touch would let
    # all five warn at once on the first edit of every session.
    STAMP="$CLAUDE_PLUGIN_DATA/no-python-warned-$SESSION"
    if ! mkdir "$STAMP" 2>/dev/null; then
        exit 0
    fi
    # POSIX-portable prune (-mtime, not GNU -mmin): stamps older than the
    # same two-day TTL the Python session stamps use age out here too.
    find "$CLAUDE_PLUGIN_DATA" -name 'no-python-warned-*' -mtime +1 -exec rm -rf {} + 2>/dev/null
fi

printf '%s' '{"systemMessage":"roll-call needs Python 3.11 or newer on PATH and could not find one. Its guards are inactive until that is fixed. Install Python 3.11+, or run /roll-call:doctor for details."}'
exit 0
