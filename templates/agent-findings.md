# Agent findings ledger: what was claimed, and whether it survived

**This is a track record, not a work queue.** It grows forever and is never
pruned. Every agent is instructed to read it before answering, and its value is
precisely that it contains entries where a seat was confident and wrong.

**A verified finding nobody has built yet does not belong here.** That is a
different artifact with a different lifetime: put it in
`.claude/findings-<seat>-<topic>.md`, name it from `slice.md`, and delete that
file when the queue empties. Mixing the two turns a permanent record into a
to-do list that nobody trusts.

## How to write a row

- **The claim as the agent stated it**, not a summary that smooths it.
- **The verdict:** `HELD` (reproduced), `REFUTED` (did not reproduce),
  `UNVERIFIED` (acted on without reproduction: record this honestly, it is the
  most useful category), or `PARTIAL`.
- **The reproduction**: the command, the measurement, or what was read. If the
  claim was acted on without one, say so plainly.
- **What the error actually was**, for a refuted claim. "Wrong" is not a lesson;
  "the tick-count harness closed its sampling window before the worker entered
  the C call" is.

## Ledger

| Date | Seat | Claim | Verdict | Reproduction | What the error was |
|---|---|---|---|---|---|
| {{YYYY-MM-DD}} | {{seat}} | {{claim}} | {{HELD/REFUTED/UNVERIFIED}} | {{command or measurement}} | {{for refuted}} |

## Standing observations

<!-- Patterns across rows, added when one becomes visible. These are what turn a
     log into a brief. Examples of the shape:

     * A seat whose claims about tool behavior hold, and whose claims about
       performance do not, should be asked for measurements more aggressively.
     * Two seats converging has never been wrong here. One seat correcting
       another has been wrong once. -->
