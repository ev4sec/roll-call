# {{PROJECT}}

<!-- INSTANTIATION: this file is auto-loaded into every primary session and is
     the root of the whole document set. Everything else is reachable from here
     or from the two files it names.

     Keep it a CONSTITUTION, not a manual. It holds what must not change and
     what has been decided. How work is done lives in the operating procedure;
     what is on the bench lives in the board.

     The rule that keeps this file honest: **anything here that governs a
     decision must be diffed against reality by a test.** See
     `tests/test_doc_contract.py`. A section nothing checks will drift, and a
     gate reading a drifted section returns confident wrong verdicts rather than
     erroring. -->

{{One paragraph: what this is, who uses it, and what it replaces. Written so
someone who has never seen the repository can route a question after
reading it.}}

## Non-negotiable constraints

<!-- Each one marked permanent or revisitable. "Permanent" means it is not a
     trade-off any agent may make, and the commercial seat is explicitly barred
     from pricing it away. Give the reason, briefly: a constraint whose reason
     is missing gets retired by whoever next sees only its cost. -->

- **{{constraint}}** *(permanent)*: {{what it forbids, and why}}
- **{{constraint}}**: {{...}}

## Identifiers

- Product name: {{PROJECT}}
- Package / distribution name: `{{slug}}`
- Import path: `{{slug}}`
- CLI command: `{{slug}}`
- Repo: {{url}}

## Licensing and posture

{{What the license is, and what the business intent is. These two must agree,
and `approval-judge` checks them against each other as a standing duty, because
on the origin project they disagreed for four days past six agents and 978
tests.}}

## Stack

- {{language, framework, database, test runner}}

## Core architecture

{{The two or three decisions everything else is built on, each with its reason
and what it forecloses. Not an inventory of modules.}}

## Data model

**This list is enforced, not descriptive.** `tests/test_doc_contract.py` parses
it and fails if it disagrees with the code in either direction. It is written
down here because the approval gate reads it to decide whether a proposed field
is *implementing* a recorded contract or *changing* one.

{{The entities and their fields. For anything non-obvious, say what the field
means and why it exists rather than restating its type.}}

## Conventions

- {{file size, typing, logging, test expectations}}

## Working agreement

- **Propose before implementing** anything that changes the data model, a public
  interface, or a published schema. **The proposal goes to the owning agent, and
  that agent's specification is the approval.** Nothing here is built
  unproposed, and nothing waits on the maintainer either. See the Prime
  directive in `.claude/operating-procedure.md`, which is exhaustive about the
  three things that still reach them.
- **Commit freely; gate the irreversible.** The full rules are in
  `.claude/operating-procedure.md`, which is their only home. They are
  deliberately not inherited from any other project.
- Never add a dependency without saying why in the same message.

## Operating procedure

The standing operating procedure for this project, covering how to route work
through the review agents, the sprint structure, and the blocker ladder, is
loaded here:

@.claude/operating-procedure.md

## Where the engine lives

Two halves, and the split matters when something needs changing.

**The machinery ships with the roll-call plugin** and is read-only: the hooks
that enforce routing, guard publication, scan edited files, write the
consult ledger, queue each seat's claims for a verdict, and read all of that
back to a session whose context was rebuilt. Update it with
`/plugin update roll-call`.

**Everything under `.claude/` in this repository belongs to this project**,
including the agent definitions in `.claude/agents/`. Edit them freely. They are
checked in, they are reviewed like source, and a plugin update will not
overwrite them. If a seat gives generic advice, the fix is to teach it about
this codebase in its own file.
