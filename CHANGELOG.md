# Changelog

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
