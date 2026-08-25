---
description: Propose a new agent for the roster, holding it to the standard-of-evidence bar. Adds the seat, or records why it was parked.
argument-hint: [what the new agent would do]
allowed-tools: Read, Glob, Grep, Write, Edit
---

# Propose a seat: $ARGUMENTS

A roster grows by default. Every gap looks like it wants an agent, and adding
one always feels like progress. It usually is not, and the cost is paid later:
each seat is a fixed tax on every consult round, and a roster of fifteen where
nine would do means nobody is asked properly because asking everybody is too
expensive.

So this command exists to say no well, and to make the no useful.

## The bar

From the operating procedure:

> An agent earns a seat only if it brings a **distinct standard of evidence**.
> Not a distinct topic, but a distinct way of being right.

A topic is not a standard. "Database expert" is a topic, and
`systems-architect` already answers it by the same means it answers everything
else. "The priced alternative" is a standard, which is why
`commercial-strategist` has a seat that nothing else can cover.

Test it by asking what evidence this seat would produce that no current seat
can. If the answer is the same kind of evidence about a different subject, it is
not a seat. It is a paragraph in an existing agent's definition.

## Procedure

**1. Read the current roster.** Every file in `.claude/agents/`, and the
`parked-roles.md` register. Pay attention to the "Distinct from X, which..."
clause each definition carries. Those clauses are the roster's map of itself.

**2. Check whether it has already been proposed.** `parked-roles.md` records
roles considered and not adopted, each with the trigger that would make it
right. If this one is there, the real question is whether that trigger has now
fired. That is a much better question than the original one and it is often the
whole answer.

**3. State the standard of evidence in one sentence.** If you cannot, stop.
That difficulty is the finding, not an obstacle to route around.

**4. Test it against every existing seat.** For each, say what that seat would
produce on the same question and why it is not enough. If any current seat
covers it, the answer is an edit to that agent's definition, not a new file.

**5. Check the tool grant.** A seat's tools must match the standard it is asked
for. An agent expected to produce measurements needs `Bash`; one that must never
mutate the tree should not have it. A mismatch here produces confident answers
with nothing behind them.

## If it earns a seat

- Write `.claude/agents/<name>.md` in the roster's house style: frontmatter with
  `name`, `description`, `tools`, and `model`; a description that includes the
  **"Distinct from X, which..."** clause; an instruction to read
  `.claude/agent-brief.md` first; and an explicit statement of what the seat
  does *not* do.
- Add at least one rule to `.claude/routing.toml` naming it. **A seat nothing
  routes to will never be consulted**, and an agent the mechanism never summons
  is decoration.
- Set that rule to `advised` first. Watch it for a week before promoting it.
- Add the reciprocal "Distinct from" clause to any existing agent whose
  boundary this narrows. Boundaries are stated on both sides or they drift.

## If it does not

Add it to `.claude/parked-roles.md` with **the trigger that would make it
right**: the concrete change in the project after which this becomes a real
seat.

This is not a consolation prize. "No" and "not yet" are different answers, and a
rejected idea with no record gets re-proposed from scratch every few months, at
full cost, by someone who was not there the first time.
