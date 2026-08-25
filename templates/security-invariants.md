# Security invariants: numbered, cited, and each one either tested or marked

**Cite an ID rather than restating a property from memory.** That is the whole
reason this file exists: an invariant that lives in a transcript cannot be
checked against later, and a property restated from memory drifts from the one
that was actually agreed.

**An invariant with no test is a wish.** Every entry carries a status, and
`test-strategist`'s standing job is to walk this register against the suite and
report the gaps.

## ID format

`{{PREFIX}}-INV-<n>`, allocated sequentially and never re-used. A retired
invariant keeps its number and gains a RETIRED status with the reason, because
a gap in the sequence is a question nobody can answer later.

## Status vocabulary

| Status | Means |
|---|---|
| `TODO` | Agreed, not implemented. |
| `PARTIAL` | Implemented, not fully proven: say which part is unproven. |
| `DONE` | Implemented **and** named test proves it. A DONE with no test named is a finding. |
| `RETIRED` | No longer holds. The reason and the date are mandatory. |

## Register

### {{PREFIX}}-INV-1: {{one-line property, stated so it can be false}}

**Status:** TODO | PARTIAL | DONE (`tests/test_x.py::test_y`) | RETIRED

**Why it holds:** {{the argument, and the cost of it not holding.}}

**The measurement:** {{if the invariant came from a measurement, put the numbers
here rather than the conclusion. "The measurement, not the conclusion" is the
rule; a number survives an argument and a summary does not.}}

**How it could regress:** {{the change that would silently break it. This is
what the test must catch.}}

---

<!-- Add entries in the same shape. Two habits worth keeping:

     * Write the invariant so it can be FALSE. "Input is validated" cannot fail;
       "nothing outside src/x/net imports an HTTP client" can.
     * When a finding turns out to be a bug class rather than a bug, it becomes
       an invariant here, and the finding row in agent-findings.md points at it. -->
