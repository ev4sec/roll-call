---
name: write-doc-contract
description: Turn tests/test_doc_contract.py from a skipped template into a live test that diffs a governing document against the code. Use when setting up roll-call, when /roll-call:doctor reports the doc contract is unfilled, when a document that a gate reads has drifted from reality, or when adding a new section to CLAUDE.md that agents will reason from.
---

# Make a governing document check itself

`tests/test_doc_contract.py` ships **skipped**. That is deliberate, and it is
the only piece of the engine that arrives unfinished on purpose, because the
thing it tests is different in every project. Its own header calls it "the
single highest-value pattern in the engine."

Leaving it skipped is the most common way an install ends up looking complete
and being hollow.

## The failure it prevents, exactly as it happened

An approval gate decided PROCEED versus APPROVAL REQUIRED by reading the data
model recorded in `CLAUDE.md`. That document had drifted from the code **in both
directions**: six shipped fields were not listed, and five listed fields had
never existed.

Nothing broke. No test failed. The gate kept answering, confidently, from a
description of a system that did not exist. Six agents and 978 tests did not
notice, because every one of them was checking the code against itself and the
document against nothing.

**A document that governs a decision and is checked by nothing does not error
when it drifts. It returns confident wrong verdicts.** That is worse than having
no document, because a missing document gets noticed.

## What deserves a contract

Not every document. The test is for a document that something **reads to make a
decision**. Ask: if this section were wrong, would a gate approve something it
should have stopped, or stop something it should have approved?

Usually qualifies:

- The data model in `CLAUDE.md`, if the approval gate reads it to tell
  *implementing a recorded contract* from *changing one*.
- A declared public interface, CLI surface, or plugin contract.
- The licensing and posture statement, if a seat checks declaration sites
  against recorded intent.
- The security invariant register, where each entry claims a tested property.

Usually does not:

- Narrative, rationale, and history. `LESSONS.md` records what was learned; it
  governs nothing directly.
- The board. It is a snapshot by design and no test can catch staleness anyway.
- Anything aspirational. A roadmap that disagrees with the code is doing its job.

## Writing one

**1. Pick the document and the section.** One section, precisely bounded by its
heading. Contracts over whole files rot.

**2. Decide what reality means.** This is the real work. Reality has to be
something you can read mechanically and that cannot silently agree with a wrong
document. For a data model that is the mapped columns on the ORM classes. For a
CLI it is the registered subcommands. For invariants it is the tests that claim
to enforce them.

If reality is only obtainable by running the tool, run the tool. The engine
already makes that argument elsewhere: when a claim is about what a tool does,
reasoning about its documented behavior is not evidence.

**3. Parse the document, do not restate it.** The test must read the actual
file. A test carrying its own copy of the expected list has created a third
thing to drift, and it will drift toward the document rather than the code.

**4. Fail in both directions.** This is the part people skip, and it is where
the original failure lived. Assert that everything documented exists, **and**
that everything that exists is documented. A one-directional test would have
caught five of that bug's eleven discrepancies and reported success.

**5. Fail with the difference, not with a boolean.** The message should name
what is in the code and missing from the document, and the reverse, by name. A
red test that says `assert False` costs a person twenty minutes to re-derive
something the test already knew.

## Before you finish

- The test **runs**. It is not skipped, and it is not passing vacuously because
  a parse returned an empty set. Break the document on purpose and confirm it
  goes red.
- It fails in both directions. Add a field to the code without documenting it,
  and confirm.
- The failure message names the specific drift.
- Remove the skip marker and the template scaffolding. A test file that still
  contains a placeholder is one somebody will assume is finished.
