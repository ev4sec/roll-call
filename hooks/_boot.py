"""Version gate and in-process launcher for every hook.

`run.sh` used to prove an interpreter was 3.11 or newer by running a one-line
probe in it, and then start a second interpreter to run the hook. Two Python
startups per hook, five hooks per edit. This file replaces the probe: the
interpreter that would run the hook checks its own version first, and if it is
new enough it runs the hook in the same process.

**Exit code 3 means "too old, try the next interpreter".** `run.sh` moves on
to its next candidate when it sees it, and nothing here reads stdin before
deciding, so the hook's payload is still intact for whichever interpreter
finally runs it. No hook may exit 3 for any other reason.

**Why the syntax here is old.** This file has to parse on whatever `python`
happens to be first on the PATH, including one too old to run roll-call, so
that the answer is an exit code rather than a SyntaxError. No f-strings, no
annotations, nothing newer than Python 2.7 understands.

Usage: python _boot.py <hook.py> [args...]
"""

import sys

MINIMUM = (3, 11)


def main():
    if len(sys.argv) < 2:
        return 0
    if tuple(sys.version_info[:2]) < MINIMUM:
        return 3
    target = sys.argv[1]
    # The hook sees exactly the argv it would have seen when run directly.
    sys.argv = sys.argv[1:]
    import runpy
    # A hook that ends with `sys.exit(main())` raises SystemExit here, and it
    # propagates out as the process exit code. That is the intent.
    runpy.run_path(target, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
