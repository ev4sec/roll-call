# The board: what is on the bench right now

**This is the first file every agent opens.** A stale board is a wrong map
multiplied across the whole roster, so it is updated at a slice boundary or a
wind-down checkpoint, before the work is parked. Not every commit.

`tests/test_process_docs.py` proves this file is *reachable*. Only the update
step keeps it *true*, and no test can catch a board that is merely out of date.

<!-- INSTANTIATION: keep the four sections. They answer, in order, the four
     things an agent needs before it can answer anything: what exists, what is
     being built, what is next, and what has already been decided so it is not
     re-derived. -->

## Current sprint

**Item:** {{PLAN_ITEM_ID}}, {{one line}}

**Done-when:** {{the checkable condition that ends this sprint. Written before
the sprint opened. If it cannot be checked, it is not a done-when.}}

**Phase:** Open | Build | Close | Land

**Open blockers:** {{named, with the ladder rung each one reached, or "none"}}

## Built and verified

<!-- What actually exists and is proven, newest first. The bar is "verified",
     not "written". Something here should be citable in place of re-deriving it. -->

- {{thing}}, {{what proves it}}

## Next, in order

<!-- Order matters more than the list. If two items could swap without cost,
     say so; if they could not, say what forces the ordering. -->

1. {{next item}}, {{what forces it to be next}}
2. {{...}}

## Settled for this slice: do not re-derive

<!-- The highest-value section and the one most often skipped. Every row here is
     a question somebody paid to answer. A row costs a line; re-asking costs a
     round trip and dilutes the next answer. -->

| Question | Answer | Settled by |
|---|---|---|
| {{question}} | {{answer}} | {{seat / measurement / date}} |
