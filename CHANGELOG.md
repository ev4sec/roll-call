# Changelog

## 0.3.0 (2026-09-11)

A guard for the one moment nothing fired: the context being rebuilt. And
the last honor-system record in the engine becomes machinery.

- **Context-loss compaction guard.** The failure this plugin was built
  around is an instruction read at session start and gone by the third
  edit. A compaction is a session start in the middle of the work, and until
  now the engine was silent at it: whatever the router had demanded, whatever
  had already been consulted, whatever an agent had edited unreviewed, all of
  it was at the mercy of a summary nobody reviewed. A new `SessionStart`
  hook fires on every compaction, resume, fork, clear, and startup, and reads
  the engine's own ledgers back to the session: the consults the router
  demanded earlier in the session that are still not on the ledger, the seats
  consulted inside the freshness window so a round is not paid for twice, the
  agent edits the commit guard has not shown yet, and the claims waiting for
  a verdict. It prints only when there is something to print, and every line
  names the file the full record lives in. The owed consults come from the
  router's own per-session state, so the brief cannot disagree with the
  router about what is fresh. The hooks cannot stop a context from being
  rebuilt; they can make sure the rebuilt one is told what they know.
- Every labeled claim a seat makes is queued the moment the seat finishes.
  A new hook on `SubagentStop` reads the seat's final report, pulls out each
  `[verified]`, `[measured]`, `[read]`, `[reasoned]`, and `[asserted]`
  claim, and appends it to `.claude/.pending-findings` with the seat and the
  time. A report with no labels gets one row saying so, because a seat that
  ignores the brief should show up as one rather than as a seat with nothing
  to say. A report is capped at twenty rows and the cap is written into the
  queue, never applied silently. Subagents that are not seats in
  `.claude/agents/` leave nothing. The verdict column is still yours: the
  hook records what was claimed, not whether it held. Init adds the queue to
  `.claude/.gitignore`; an existing install adds the line `.pending-findings`
  by hand.
- Doctor gains a section on the roster's track record, backed by
  `scripts/seat_stats.py`. It tallies the verdict column of
  `agent-findings.md` per seat and reports only what crosses a threshold: a
  seat whose reproduced claims are refuted two times in five, a seat whose
  claims are mostly acted on unverified, and a queue that holds rows or has
  gone stale. The reconcile-board skill works the queue: each row becomes a
  ledger row with a verdict, or is dropped by someone who read it.
- The validation harness grows to 40 checks, driving the two new hooks
  through `run.sh` the way the harness will.

## 0.2.2 (2026-09-01)

Scope and ecosystem fixes from a full review of the shipped plugin.

- Every hook now checks for `.claude/engine.toml` before doing anything, so
  the guards run only in repositories that have been set up, and an empty
  `.claude/.roll-call-ignore` opts a repository out of all of them. The
  plugin installs at user scope, and "nothing happens until init runs" is
  now what the hooks do rather than what the session-start message says.
- The dependency audit picks its auditor by ecosystem: Python manifests go
  to pip-audit, Node manifests to npm audit against the lockfile, and an
  ecosystem without its auditor is reported as unchecked. `requirements.txt`
  is read when there is no `pyproject.toml`, and `[dependencies] enabled`
  switches the audit off.
- The test hook runs a non-Python suite the way `engine.toml` describes it:
  with an empty interpreter, a command whose first entry is a program name
  runs that program.
- Init writes `.claude/.gitignore` so the consult ledger, the post-agent
  marker, and the fire-rate ledger stay local to each checkout instead of
  being committed and shared. The scaffold now writes 30 files.
- The post-agent commit prompt shows only the source files that changed
  while an agent ran, using a snapshot taken before the agent starts, and
  stays silent when the agent changed nothing under the source root. Without
  a snapshot it shows the whole source diff as before.
- The security scan reports a fixture password or a debug flag inside a test
  file as a warning rather than a block; the same line in product code still
  blocks.
- `run.sh` probes `python` before `python3` on Windows, where the latter is
  usually a placeholder, saving a wasted launch on every hook.
- The router's scope is documented: it sees writes made through the editor
  tools, not files changed by shell commands or git operations. The README,
  the routing table, and the operating procedure all say so.
- Init tells the user that `test_permanent_refusals.py` fails on purpose until
  its list is filled, so the first red test run is expected.
- `pytest` run from the plugin root collects only the plugin's own suite; the
  project-side templates under `templates/tests/` are no longer collected.
- The manifest names the repository and homepage.

## 0.2.1 (2026-08-31)

Closes everything 0.2.0 shipped as reported rather than fixed.

- A rule that names a doc or lockfile exactly now fires. The suffix gate
  (.md/.txt/.lock, now case-folded) still drops churn before matching, but a
  literal entry like ".claude/slice.md" is a deliberate act the router
  honors, with backslashes, a leading ./, and platform case folded before
  comparing so a spelling variant cannot silently kill a gate. The four
  0.1.0 rules that could never fire (board, roadmap, vision, constitution)
  now enforce, and posture's README.md leg joins the LICENSE and NOTICES
  legs that always fired. Glob patterns over ignored suffixes stay
  permanently silent, and the spend report flags rules built only from
  those. Doctor's dead-rule check, the routing-rule skill, and init's
  seeding guidance all teach the gate now, so a rule that passes their
  checks is a rule that actually fires.
- Consult credit in the spend report is scoped to the rule by timing: a
  consult answers a rule only if that rule fired within fresh_hours
  beforehand, so one consult of a shared seat no longer vouches for rules it
  never saw.
- The no-Python warning is stamped per session instead of per day, matching
  the Python hooks' once-flags: a fresh session is told its guards are dead,
  and within a session the message does not repeat. An unparsable payload
  degrades to per-day; no data dir degrades to every invocation.

## 0.2.0 (2026-08-31)

Token-burn controls: the engine now polices its own context cost the way it
polices everything else, with the enforcement guarantee untouched. Every
required firing still exits 2, every consult still lands on the ledger, and
every fallback degrades toward more output, never silence.

- The router renders a rule's full why/question once per session; repeat
  firings still block, in one line naming the owed agents and rule ids.
  `repeat_style = "full"` restores the old behavior. Measured: about 168
  tokens per repeat down to about 51.
- Rules take an `exclude` field so a broad glob yields to the narrower rule
  that owns a path. The shipped frontend rule uses it, ending a duplicate
  spawn of roughly 5,000 tokens on api-owned TypeScript files.
- The advised level's documented "mentioned once" is now implemented: once
  per session.
- The router writes a hook-only fire-rate ledger (`.claude/.route-stats`,
  pruned to 30 days), and `scripts/route_stats.py`, run by doctor's new
  section 7, reports required rules being fired at and ignored, plus
  documents outgrowing the expensive read paths.
- Doctor's template-drift check runs as `scripts/drift.py`, a tested
  subprocess diff that re-applies init's substitutions, replacing a
  paired-Read procedure that could pull 30k+ words into context.
- The backend-tests timeout advisory and the pip-audit-missing finding teach
  in full once per session, then collapse to one line that still says the
  condition holds. run.sh's no-Python warning fires once per day per machine,
  which its own comment had claimed since 0.1.0.
- Seven seats cite the CLAUDE.md the harness already injects instead of
  re-reading it, and vision.md is read on demand outside the three
  vision-lane seats, always with a declared skip.
- security-engineer and practitioner-critic report at most five findings in
  full, one line each below the cut, and raw scanner output stays out of
  reports.
- The measurement traps move from agent-brief.md, which every seat reads on
  every consult, to `.claude/measurement-traps.md`, read only before a
  `[measured]` claim. The scaffold now writes 29 files.

Held deliberately, pending evidence from the fire-rate ledger: consult
waivers (the one control that could silence a required rule) and rotation of
the findings ledger. The operating-procedure core/annex split is parked for a
later release.

Known issue, carried from 0.1.0 and now reported instead of silent: the
router drops .md/.txt/.lock edits before rule matching, so shipped rules
aimed only at such paths (the board, roadmap, vision, and constitution
gates) cannot fire. Doctor's section 7 names them; the fix, honoring a rule
that explicitly targets an ignored path, is planned for the next release so
it can go through its own review rather than shipping unreviewed.

## 0.1.0 (2026-08-24)

Initial public release.

- Nine specialist review agents, installed into the project as editable files
  rather than shipped read-only.
- Consult routing: `routing.toml` maps paths to owning agents, a hook checks
  the ledger on every write, and a `required` rule blocks until the owner has
  actually been consulted.
- A consult ledger written by machinery, not by hand.
- Guards: publish gating by destination, security scan of edited files, test
  runner, dependency audit, built-artifact inspection, unreviewed-agent-edit
  review.
- `/roll-call:init` scaffolds a project without overwriting anything the user
  already has; `/roll-call:doctor` finds guards that are silently asleep;
  `/roll-call:seat` holds new agents to the standard-of-evidence bar.
- Three skills: board reconciliation, routing-rule authorship, document
  contract authorship.
- 113 plugin tests and a 35-check end-to-end validation harness.
