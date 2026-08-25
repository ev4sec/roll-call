---
name: write-routing-rule
description: Write or revise a rule in .claude/routing.toml so it fires when it should and stays silent otherwise. Use when adding a rule, when a rule is firing too often or never firing, when promoting a rule from advised to required, or when /roll-call:doctor reports a dead or overbroad rule.
---

# Write a routing rule that survives a busy week

The routing table is the highest-leverage file in the engine and the easiest one
to ruin. A good rule catches the change that would have been expensive to get
wrong. A bad one fires on every edit in a busy directory, gets muted within a
day, **and takes the credible rules down with it.** That last clause is the part
people miss: the cost of a noisy rule is not the noise, it is the trust it
spends on behalf of every other rule in the file.

The table is data rather than prose for a reason worth remembering. This project
kept its routing in a paragraph once. It was read at session start and gone by
the third edit, and the session that shipped a schema change, split two modules,
relicensed the project and altered the roster itself consulted **zero agents**.
Every one of those was named in that paragraph.

## The bar for a new rule

Both must be true.

1. **The decision is expensive or hard to reverse.** A shipped column is a
   migration. A released version number can never be reused. A published
   interface is a promise to people who are not in the room. Ordinary code that
   can be changed again next week does not need a gate.
2. **The owner is not the session doing the work.** Routing exists to bring in
   judgment the author does not have. A rule that sends a change to the person
   already making it is ceremony.

If a rule would fire on most edits in a normal day, it fails regardless of how
important the surface is. Narrow the paths until it does not.

## Fields, and what a good one looks like

**`paths`** are globs against repo-relative POSIX paths. Aim at the specific
files where the decision lives, not the directory they sit in. `src/**/*.py` is
almost always wrong. `src/*/store/models.py` is usually right.

**`agents`** names seats that must exist in `.claude/agents/`. More than one
means ask them **in parallel**, in a single message. Never serially. Keep it to
two at most; four seats on one change means the change is too broad to route and
should be narrowed instead.

**`question`** is where most rules fail. Name the decision and demand the answer
in a usable shape. Routing that names an agent but not a question produces a
survey, and the engine needs a recommendation stated as the thing to build.

Weak: *"Review this change to the data model."*

Strong:

> This change adds, removes, renames or reclassifies a mapped column. State the
> decision as the thing to build: the column, its type, nullability, its
> classification and why, and whether it forces a format version bump. Price the
> alternative.

The difference is that the second one cannot be answered with an opinion.

**`level`** is `advised` or `required`. **Start at `advised`, always.** Watch it
fire for a week. Promote it only after it has caught something real, and only if
it has stayed quiet the rest of the time. A rule that goes straight to
`required` on the strength of an argument is how the table earns its first mute.

**`why`** is the cost of skipping, in one concrete sentence. This is what the
reader sees when the rule fires and they are deciding whether to care. Write it
for the version of yourself that is tired and in a hurry. Not "the data model is
important" but "a shipped column is a migration and a re-triage of every
historical finding."

## Diagnosing a rule that is not working

**Never fires.** Check the globs against the real tree first. Dead rules
outnumber every other kind of failure, and they are invisible: nothing errors,
the seat simply never gets summoned. `/roll-call:doctor` lists them.

**Fires constantly.** The paths are too broad, or the surface genuinely does
change every day, in which case it was never a gate. Narrow it or delete it.
Lowering it to `advised` and leaving it noisy is the worst option: it keeps the
noise and gives up the enforcement.

**Fires correctly and gets ignored.** The `question` is not specific enough to
be worth answering, or the `why` does not explain the cost. Rewrite those two
fields before touching anything else.

## Before you finish

- Every named seat exists in `.claude/agents/`.
- The globs match at least one real file **right now**. Check, do not assume.
- The rule `id` is unique.
- `question` and `why` are both non-empty and specific to this project.
- You added the rule rather than broadening an existing one. Widening a working
  rule to cover a new case is how a precise rule becomes a noisy one.
