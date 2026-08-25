# Lessons: things that cost something to learn

A resume note is for one handoff and gets deleted when the work finishes. **This
file is the opposite: it outlives the task.** Without it, the same tool bug gets
rediscovered at the same cost, three sessions apart, by the same person.

**Write at the moment of discovery, not at wind-down.** By wind-down the detail
that made it useful is gone. One line is a valid entry.

## What goes in

- **Tool and harness behavior that is not in the docs**, especially where a
  tool is silently wrong rather than loudly broken. Record the *observed*
  behavior, the *reproduction*, and the *workaround*, and mark clearly where
  the workaround is empirical rather than understood.
- **Automations that paid for themselves.** Include the script or the exact
  command, not a description of it.
- **Recurring mistakes.** If the same error has been made twice, it is a pattern
  and belongs here, written plainly. This is the highest-value section and the
  one there is most temptation to soften.
- **Calibration facts**: thresholds, limits, rates, budgets discovered by
  hitting them.
- **Decisions with their reasoning**, where re-litigating them would be
  expensive.

## What does not

Anything the code or the project's own instructions already state; the narrative
of what happened (that is the run log); anything still uncertain, unless
labeled as uncertain.

## The failure mode this file exists to prevent

**A finding recorded somewhere that does not govern.** A rule written into an
audit trail is not operative. When a lesson implies a change to how work is
done, propagate it to the file that actually controls that work *and* note it
here. This file records the discovery; it does not enforce it.

---

## Entries

### {{YYYY-MM-DD}}: {{one-line title}}

**Observed:** {{what actually happened, with the numbers}}

**Reproduction:** {{the exact command or steps}}

**Workaround:** {{what to do instead}} *(understood | empirical)*

**Propagated to:** {{the file that now enforces it, or "nothing yet. This is
still just a story"}}
