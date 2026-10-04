---
name: find-roster-gap
description: Walk the work that is coming and find what no seat on the roster owns, then hand each real gap to /roll-call:seat as a one-sentence standard of evidence. Use at a slice boundary, before a roadmap or planning conversation, when a new kind of work is about to start, when a seat keeps answering questions outside its own standard, or when someone asks whether the roster is missing someone. Not for judging an agent someone has already proposed; that is /roll-call:seat on its own.
---

# Find the seat nobody has proposed

`/roll-call:seat` judges a proposal. It cannot find one. And
`.claude/parked-roles.md` names the blind spot that leaves:

> This file is structurally blind to the role nobody thought of. It records
> roles that were proposed and declined. The most valuable seat added to the
> origin roster had never been proposed at all.

The fix it prescribes is the procedure here: **walk the work that is next and
ask who owns it**, rather than walking the roster and asking what to add.

## The one thing to be careful about

**You are finding a question, not making a case.** `/seat` exists to say no
well, and it can only do that if what reaches it is evidence rather than
advocacy. So do not draft an agent file, do not name the seat, and do not argue
that the gap is real. Bring the work item, the seats you tested against it, and
where you found it. A gap that needs persuading to look like one is usually an
edit to an existing seat.

The opposite mistake costs as much. Most walks end with every item owned. That
is the common answer and a good one; report it in a line and stop.

## Walk the work

Read the roster first, but only the frontmatter `description` of each file in
`.claude/agents/`: the "Distinct from X, which..." clauses are the map you test
against. Then gather the work from the repository:

1. **What is next.** The "Next, in order" section of `.claude/slice.md`. Each
   item is a decision someone is about to make. A design seat's trigger is the
   first decision in its domain, not the first artifact, so a decision with no
   owner today is a gap today.
2. **What could be pulled forward.** Items in `.claude/roadmap.md` whose
   "What would pull it forward" trigger has fired or is close, and decisions in
   `.claude/architecture.md` whose "What would reopen it" fact has turned up.
   Both are work arriving that nobody scheduled.
3. **Surfaces under change that nothing routes.** Directories with recent
   commits that no rule in `.claude/routing.toml` matches. Unrouted is not the
   same as unowned, but it is where unowned work hides.
4. **Claims nobody could check.** Rows in `.claude/agent-findings.md` left
   `UNVERIFIED`, and claims a seat labeled `[asserted]` outside its own lane.
   A seat guessing where it should measure is the clearest sign the right
   standard is missing.
5. **Parked triggers.** For each role in `.claude/parked-roles.md`, has the
   trigger it names now fired? That is a better question than any new
   proposal, and it is often the whole answer.

## Test each item

For every item, name the seat that owns it and **the kind of evidence that seat
would produce** on it. Then sort it:

- **Owned.** A seat answers it by its own standard. Nothing to do.
- **Owned by a stretch.** A seat could answer, but only by a standard that is
  not its own: a constraint reader asked to measure, a measurer asked to price.
  This is not a seat. It is an edit to that seat's definition, or a routing
  rule that sends the question somewhere better. Say which.
- **Unowned.** No seat produces the evidence the decision needs. Write that
  evidence as **one sentence**: what this seat would be right about, and how.
  If the sentence will not come, the item is not a gap yet; say what is
  missing instead of forcing it.

## Hand off

For each unowned item whose sentence holds, run `/roll-call:seat` with the
sentence as the argument, one gap per run. Give `/seat` the work item and the
seats you tested, then let it rule. It reads the parked register and tests the
sentence against every seat again, and it may well say no. That is the gate
working, not this skill failing.

## Deliver

A short table: item, owning seat or "unowned", and the evidence that seat would
produce. Under it, the stretch edits you recommend and the gaps handed to
`/seat`. If every item is owned, one line saying the roster covers the work
ahead, and nothing else.
