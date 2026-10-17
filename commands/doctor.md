---
description: Check that roll-call is actually working in this repository. Reports dead routing rules, silent hooks, unfilled placeholders, and template drift.
allowed-tools: Read, Glob, Grep, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py:*), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py:*), Bash(py -3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py:*)
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

## 1. Run the script once

Run `scripts/doctor.py` from `${CLAUDE_PLUGIN_ROOT}` with `python3`, passing
`--target` as this repository's root. If that spelling is missing or the
script exits 3 (the interpreter reported itself older than 3.11), try `python`,
then `py -3`. Run it once. **Do not probe `--version` separately**; the script
reports on the interpreter it is running under, which is the only answer that
matters.

- If no spelling gets past the version line, that is the headline. Every hook
  is inert. Nothing else matters until it is fixed, so say that first and keep
  the rest brief.
- If the script exits 2, roll-call was never set up here. Say so and point at
  `/roll-call:init`.

Everything mechanical is in that one output. **Do not redo any of it by hand**:
do not Glob the routing globs, do not Grep for placeholders, and do not Read
`.claude/.consults`, `.claude/.route-stats`, or `.claude/.pending-findings`.
They are machine files, and the script exists so their contents never need to
enter anyone's context. Your job is to read the blocks and say what they mean
for this project.

## 2. What each block is telling you

**`[config]`** is whether the project is described. A template value still in
`engine.toml`, a source root or test directory that does not exist, a runner
not on PATH: each one is a hook watching nothing. Name the fix.

**`[rules]`** is the most valuable block. A rule that matches no file is a seat
nobody will ever be sent to. A rule naming a seat with no file blocks on a
consult that cannot happen. A rule matching a large share of the tree will be
muted and take the credible rules with it. An exclude that leaves real files
covered by nothing is a hole wearing a boundary's name. A seat no rule names is
decoration. If every rule is still `advised` long after init, say so once,
without nagging; the posture line already does.

**`[placeholders]`** is what the engine still does not know. Weight them: a
missing `{{SCALE_NUMBER}}` costs one agent some precision, while an unfilled
vision or agent definition means a seat is ruling from a blank record, which
is worse than not asking it. The block marks those. If it reports the
refusals test unfilled, that test is red on purpose and the test hook reports
it rather than blocking; a suite that is green **including** that test has
been made green by deleting a guard, and that is worth saying plainly.

**`[ledgers]`** is whether the guards are firing. An empty consult ledger in
an active repository means agents are not being consulted at all, which the
router can only report on, never cause. Consult entries that name no seat are
runs that credit no rule. A findings ledger with no verdicts is a roster with
no track record.

**`[drift]`** compares the machinery prose against the shipped templates after
re-applying init's substitutions. roll-call never rewrites files in a
repository, so a template that moved ahead is reported, not applied. Name the
file and summarize from the script's line. **Do not offer to overwrite
anything**, and read a template and local pair side by side only when the user
asks about a named drift. Config and the living record documents are not
compared; their divergence is the install working.

**`[routing]`** is what the routing is costing: a required rule fired at and
ignored, or a document growing in one of the expensive read paths. A rule
being ignored is the script's finding to make, not an impression to form by
scrolling a ledger.

**`[seats]`** is the roster's track record: a seat whose reproduced claims
keep failing, a seat whose claims are mostly acted on unverified, and the
claims still waiting for a verdict. A waiting claim is a reproduction task for
the reconcile-board skill, not a doctor finding; here, only say how many there
are and how long the oldest has waited.

## 3. Output

Group by severity:

- **Broken.** A guard that cannot run. Name the fix.
- **Asleep.** A guard that runs but can never fire. Usually a dead rule.
- **Unknown.** Judgment the engine is missing, ordered by which seat it disables.
- **Drift.** Templates that moved on.
- **Waiting.** Claims in the queue with no verdict, and any seat the track
  record says to check before believing.

If everything is healthy, say so in one line and stop.
