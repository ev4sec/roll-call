---
name: reconcile-board
description: Check the project board in .claude/slice.md against what the repository actually shows, and propose the corrections. Use when the board looks stale, at a slice boundary, before a planning conversation, or when someone asks what the current state of the project is. Also use when an agent has just given advice that seems to assume an out-of-date picture of the work.
---

# Reconcile the board with reality

`.claude/slice.md` is the first file every agent opens. It answers, in order,
what exists, what is being built, what is next, and what has already been
decided. Nine seats read it before they reason about anything.

It is also the one document in this engine that **nothing can verify**. The file
says so itself:

> `tests/test_process_docs.py` proves this file is *reachable*. Only the update
> step keeps it *true*, and no test can catch a board that is merely out of
> date.

That is the gap this skill exists to close, and the cost of the gap is not one
wrong answer. A stale board is a wrong map multiplied across the whole roster:
every seat reasons confidently from the same bad premise, and none of them can
see that they are doing it.

## The one thing to be careful about

**You are proposing, not rewriting.** The board records intent as well as fact,
and intent is not visible in a commit log. Work that stalled deliberately looks
exactly like work that was forgotten. A section marked next that has been next
for a month may be correctly parked.

So produce a diff and a set of questions. Never silently overwrite a line whose
reasoning you cannot see.

## Gather the evidence

Work from the repository, not from the board. Reading the board first anchors
you to the answer you are supposed to be checking.

1. **Commits since the board last changed.** `git log` the board file itself to
   find when it was touched, then read what has landed since. Group by surface
   rather than listing commits.
2. **Open findings files.** `.claude/findings-*.md` are verified findings nobody
   has built yet. Each one is either work in flight, work that should be on the
   board, or a file that should have been deleted when its queue emptied.
3. **The consult ledger.** `.claude/.consults` shows which seats have been busy.
   Heavy consultation on a surface the board calls settled is a strong signal.
4. **The claim queue.** `.claude/.pending-findings` holds every labeled claim
   a seat made, one tab-separated row each: timestamp, seat, label, claim.
   The hook writes it; nothing empties it but a person. For each row, either
   propose a ledger row for `agent-findings.md` with the verdict and the
   reproduction, or say it was read and dropped. Delete the rows you moved,
   so the file stays the list of claims nobody has judged. A row labeled
   `unlabeled` is a seat that ignored the brief; say so, and fix the seat.
5. **Recently fired routing rules.** Which parts of the tree have been under
   active change tells you where the work actually is.
6. **The test suite.** New test files name new surfaces. A skipped or failing
   test that the board does not mention is usually an unrecorded blocker.

## Produce four lists

- **Landed but not recorded.** Shipped, still sitting under "being built" or
  absent entirely. The most common and least harmful drift.
- **Recorded but not landed.** Listed as done, and the code disagrees. The most
  dangerous, because a gate reading it will approve work on a foundation that is
  not there.
- **In flight and invisible.** Real activity the board never mentions, usually
  discovered through findings files or the ledger.
- **Decided but unwritten.** A decision argued in a consult and never recorded.
  These belong in `architecture.md` with the reasoning and the rejected option,
  not on the board.

## Deliver

Show the proposed board as a diff against the current one, then list the
questions you could not answer from evidence. Keep the four sections the board
already has. Do not add a fifth, do not turn it into a ticket tracker, and do
not import a task list from elsewhere.

If a decision surfaced that belongs in `architecture.md` or a lesson that
belongs in `LESSONS.md`, say so and route it there. The board is what is on the
bench right now. Anything with a longer life than the current slice is somebody
else's file, and putting it here is how a board becomes a place nobody looks.
