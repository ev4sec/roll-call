# {{PROJECT}}: vision

**Authoritative on product direction, scope and priority.** Where `CLAUDE.md`
and this file disagree on scope or priority, this file wins and `CLAUDE.md` is
reconciled to it. The non-negotiable constraints in `CLAUDE.md` remain
authoritative regardless.

**This file goes stale silently, and that is its characteristic failure.** On
the origin project it was 36 source commits out of date while the data model,
the licensing posture and the delivery plan each had a contract test and the
vision had none. A gate ruling from a stale premise does not error; it returns
confident wrong verdicts. `commercial-strategist` owns reporting that drift at
each sprint Open. Nothing else will catch it.

## What this is

{{One paragraph. What the product is, in the words a buyer would use, not the
words the architecture uses.}}

## Who it is for

{{The specific person. Their job, their scarce resource, and what they do today
instead.}}

## The gap it fills

{{What exists already, and why it does not serve that person. Name the
alternatives: a vision that cannot name its competition has not been tested.}}

## Principles

<!-- Each one must be capable of refusing something. A principle that refuses
     nothing is decoration, and scope-validator will cite these when it refuses,
     so they need to be citable. -->

1. **{{principle}}**: {{what it means concretely, and what it rules out}}
2. **{{principle}}**: {{...}}

## Scope, this phase

{{What ships. Numbered, so the plan and the board can reference items.}}

## Out of scope, and why

<!-- The most valuable section, and the most deletable. Each entry says what is
     refused AND what would change the answer. "Never" and "not yet" are
     different answers and must be written differently: see parked-roles.md for
     the same discipline applied to seats. -->

- **{{thing}}**: {{why refused}}. {{What would change it, or "permanent".}}

## Permanent refusals

<!-- These are asserted as literal strings by tests/test_permanent_refusals.py.
     Retiring one is then a failing test with a name on it, rather than a diff
     nobody reads. Word them so the test can match exactly. -->

- {{refusal, worded as it will be asserted}}
