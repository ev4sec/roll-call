# Changelog

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
