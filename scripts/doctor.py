#!/usr/bin/env python
"""Run every mechanical check the doctor command reports, in one process.

**Why one script.** The doctor command used to run drift.py, route_stats.py
and seat_stats.py separately, after probing `python3 --version` by hand. That
meant three subprocesses, nine `allowed-tools` entries (one per script per
interpreter spelling), and a version probe that either prompted the user or had
to be pre-approved as an interpreter entry not pinned to a plugin file, which
the plugin directory holds for review. Here the interpreter reports on itself
and the three reports run in-process, so the command needs one entry per
interpreter spelling and nothing else.

**Why the syntax is old.** This file has to parse on whatever `python` happens
to be first on the PATH, including one too old to run roll-call, so that the
answer is a readable line rather than a SyntaxError. No f-strings, no
annotations, nothing newer than Python 2.7 understands, until the version check
has passed and the real scripts are imported.

Exit codes: 0 when the checks ran, 3 when this interpreter is too old (try the
next spelling), 2 when the target is not a roll-call install. It never writes
anything.
"""

import argparse
import os
import sys

MINIMUM = (3, 11)


def _version(info):
    return "%d.%d.%d" % (info[0], info[1], info[2])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", default=".",
                        help="Repo root of the install being checked.")
    args = parser.parse_args(argv)

    here = _version(sys.version_info)
    if tuple(sys.version_info[:2]) < MINIMUM:
        print("interpreter: Python %s at %s is older than %d.%d; roll-call "
              "cannot run under it." % ((here, sys.executable) + MINIMUM))
        return 3
    print("interpreter: Python %s at %s" % (here, sys.executable))

    project = os.path.abspath(args.target)
    if not os.path.isdir(os.path.join(project, ".claude")):
        print("doctor: no .claude/ under %s; is roll-call set up here?" % project)
        return 2

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pathlib import Path

    import drift
    import route_stats
    import seat_stats

    sections = (
        ("drift", lambda root: drift.report(root)),
        ("routing", lambda root: route_stats.report(root, route_stats.WINDOW_DAYS)),
        ("seats", lambda root: seat_stats.report(root)),
    )
    root = Path(project)
    for name, run in sections:
        print("")
        print("[%s]" % name)
        # One broken report must not hide the other two: the doctor's whole
        # job is finding the guard that fails quietly.
        try:
            lines = run(root)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            print("%s: the check itself failed (%s: %s)"
                  % (name, type(exc).__name__, exc))
            continue
        for line in lines:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
