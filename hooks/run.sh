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
# When nothing suitable is found this says so once a day per machine, in
# words, and exits 0. It must never block a tool call. A guard that cannot run
# should make its absence visible and then get out of the way, because a
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

# One warning per machine per day. This hook fires up to five times per file
# edit, and the condition cannot change mid-session without an install, so
# repeating the identical message trains the reader to scroll past the one
# copy that matters. No Python exists here by definition, so the stamp is pure
# shell; without CLAUDE_PLUGIN_DATA it degrades to warning on every
# invocation, the same direction session_start degrades.
if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    STAMP="$CLAUDE_PLUGIN_DATA/no-python-warned-$(date +%Y%m%d)"
    [ -f "$STAMP" ] && exit 0
    mkdir -p "$CLAUDE_PLUGIN_DATA" 2>/dev/null
    rm -f "$CLAUDE_PLUGIN_DATA"/no-python-warned-* 2>/dev/null
    : > "$STAMP" 2>/dev/null
fi

printf '%s' '{"systemMessage":"roll-call needs Python 3.11 or newer on PATH and could not find one. Its guards are inactive until that is fixed. Install Python 3.11+, or run /roll-call:doctor for details."}'
exit 0
