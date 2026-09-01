---
description: Check that roll-call is actually working in this repository. Reports dead routing rules, silent hooks, unfilled placeholders, and template drift.
allowed-tools: Read, Glob, Grep, Bash
---

# Check the engine

Every guard here is one that fails **silently** when it fails. A routing rule
whose paths no longer exist does not error, it simply never fires. A hook with
no interpreter does not crash the session, it returns nothing. In both cases the
user believes they are covered and they are not, which is the specific failure
this whole engine argues against.

So the job is to find guards that are asleep and say so out loud.

Report only what is wrong or unknown. **A healthy engine gets a short answer.**
A report that lists twenty passing checks trains the reader to skim it.

## 1. Can the machinery run at all

- `python3 --version`, then `python`, then `py -3`. Is one of them 3.11+?
- If not, that is the headline. Every hook is inert. Nothing else matters until
  it is fixed, so say that first and keep the rest brief.

## 2. Is the project described

- Does `.claude/engine.toml` exist and parse?
- Does `source_root` point at a directory that exists?
- Does the configured test command actually run here?
- Flag keys that look like leftovers from the template rather than this project.

## 3. Is the routing table alive

This is the most valuable section. For each rule in `.claude/routing.toml`:

- **Dead rule.** Do its globs match any file in the repository? A rule matching
  nothing is a seat nobody will ever be sent to.
- **Phantom seat.** Does every agent it names exist in `.claude/agents/`? A rule
  naming a missing agent blocks on a consult that cannot happen.
- **Overbroad rule.** Does it match a very large share of the tree? Say so.
  A rule that fires on everything gets muted, and it takes the credible rules
  with it.
- **Orphaned carve-out.** For each rule with an `exclude`, does every excluded
  path that actually exists in the tree still match some other rule's paths?
  An exclude that leaves a real file covered by nothing is a hole wearing a
  boundary's name.
- **Posture.** How many rules are `advised` versus `required`? If everything is
  still `advised` long after init, the engine is advising and enforcing nothing.
  Mention it once, without nagging.

## 4. What the engine still does not know

Count and locate the remaining `{{...}}` placeholders across `.claude/` and
`CLAUDE.md`.

Weight them. A missing `{{SCALE_NUMBER}}` costs one agent some precision. An
unfilled vision or constraints section means `scope-validator` and
`approval-judge` are ruling from a blank record, which is worse than not asking
them. Name the ones that disable a seat.

Check `tests/test_permanent_refusals.py`. If it still holds template content, it
is failing on purpose and should be. A suite that is green **including** that
test has been made green by deleting a guard, and that is worth saying plainly.

## 5. Are the guards actually firing

- Does `.claude/.consults` exist and have recent entries? An empty ledger in an
  active repository means agents are not being consulted at all, which the
  router can only report on, never cause.
- Is `.claude/agent-findings.md` growing? A permanent record with no entries is
  a roster nobody is using.
- Does `.claude/scan-rules.toml` exist? Optional, but its absence means the
  security scan is running its generic baseline only.

## 6. Template drift

roll-call deliberately never rewrites files in a repository, so improvements to
the shipped templates do not reach an existing install.

Run `scripts/drift.py` from `${CLAUDE_PLUGIN_ROOT}` with the interpreter found
in section 1, passing `--target` as this repository's root, and report its
lines. It re-applies the substitutions init performed and the note-stripping,
then diffs each shipped template against the local copy in the subprocess, so
the comparison costs the same whether the documents total two hundred words or
twenty thousand. **Do not Read template and local pairs side by side**; that
was the old procedure and it pulled 30k+ words into context on a full install,
landing on exactly the sessions already in trouble. Read a specific pair only
when the user asks about a named drift.

Where a template has moved ahead, name the file and summarize from the
script's line. **Do not offer to overwrite anything.** Describe the difference
and let the user decide, because the local copy is the one they tuned and that
is the whole reason it is theirs. The script compares only the machinery
prose (procedure, brief, traps, seats, project-side tests): the root
`CLAUDE.md` is a merged file, `engine.toml` and `routing.toml` are rewritten
by init on purpose, and the living record documents diverge because they are
being used. None of those is drift; review them by hand only on request.

## 7. What the routing is costing

Run `scripts/route_stats.py` from `${CLAUDE_PLUGIN_ROOT}` with the interpreter
found in section 1, passing `--target` as this repository's root, and report
its lines verbatim. It aggregates the hook-written fire-rate ledger against
the consult ledger and the routing table, and it prints only what crosses a
threshold: a required rule being fired at and ignored, or a document growing
in one of the expensive read paths. A healthy table gets one line.

**Do not Read `.claude/.route-stats` or `.claude/.consults` yourself.** They
are machine files, and the script exists precisely so their contents never
need to enter anyone's context. A rule being ignored is the script's finding
to make, not an impression to form by scrolling a ledger.

## Output

Group by severity:

- **Broken.** A guard that cannot run. Name the fix.
- **Asleep.** A guard that runs but can never fire. Usually a dead rule.
- **Unknown.** Judgment the engine is missing, ordered by which seat it disables.
- **Drift.** Templates that moved on.

If everything is healthy, say so in one line and stop.
