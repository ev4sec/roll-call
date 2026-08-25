# Parked roles: not rejected, not yet earned

Roles proposed and deliberately not adopted, with **the trigger that would make
each one right**. Kept because "no" and "not yet" are different answers, and a
rejected idea with no record gets re-proposed from scratch every few months.

The bar for a seat is in `.claude/operating-procedure.md`: *an agent earns a
seat only if it brings a distinct standard of evidence, not a distinct topic,
but a distinct way of being right.*

<!-- INSTANTIATION: this file starts nearly empty and fills as roles are
     proposed. The entries below are the ones whose reasoning is portable: each
     records a role that sounds obviously useful and is usually wrong, and says
     what would change that. Delete any that plainly do not apply and add the
     project's own as they are declined.

     Write each entry the same way: the trigger first, then the analysis, then
     what it would take to clear the bar. -->

---

## The two lessons this file exists to teach

**A design authority whose trigger is the existence of the artifact arrives one
decision too late.** The frontend seat on the origin project was parked with the
trigger "the first component". That trigger was wrong, and it was adopted
*before* any frontend existed: waiting for the first component means the
component architecture, the state model and the scaling strategy all get decided
by a backend-shaped reasoner and reviewed afterwards, on the one surface the
product exists to provide. **The correct trigger for a design seat is "when the
first decision in its domain is about to be made".** For a review seat, the
artifact trigger is right. Check which kind you are writing.

**This file is structurally blind to the role nobody thought of.** It records
roles that were *proposed and declined*. The most valuable seat added to the
origin roster had never been proposed at all. Six seats existed and none could
author the product's own content or rule on whether it could be sold. When
reassessing the roster, **walk the work that is next and ask who owns it**,
rather than walking this list and asking what to promote.

---

## build-assistant: an implementer subagent

**Trigger: a measured throughput problem, and a body of work that is mechanical
with a mechanical oracle.**

The generic "implements the application, integrations, database and business
logic" role is rejected on two grounds that hold across projects:

- A builder receives a hook's *block* without the argument behind the invariant,
  so the cheapest exit is satisfying the scanner rather than fixing the design.
- The parent sees only a final report, so a blocked-then-worked-around edit is
  invisible in the transcript the maintainer reviews.

**Evidence against it, from the largest mechanical-looking change on the origin
project:** roughly ten files, twenty-six call sites, four pinned vectors, and
it needed continuous judgment at almost every step. Two module splits decided
mid-change, a mutation pass to prove the new tests were not vacuous, and an
acceptance test that is worthless unless written under a non-identity input. The
share of work that is mechanical *with a mechanical oracle* did not appear, and
that share is this role's entire addressable market.

**Correction on the record:** the objection that hooks would not fire inside a
subagent was *wrong*. They do. Do not reuse that argument.

A bounded version could earn its place. Admission criteria, stated narrowly so
it cannot expand:

- The spec fits in a paragraph.
- A failing acceptance test already exists, written by the primary session.
- **No numbered invariant is in scope.**
- The work is mechanical with a mechanical oracle: a rename across N files,
  back-filling docstrings, porting a test file to a changed fixture signature.

---

## release-manager: a checklist first, a seat only if that fails

**Trigger: the second or third release, if the checklist proves insufficient.**

Most of the stated remit of a release role either already exists as machinery
(CI, the artifact check, the publish guard) or does not apply. The real gap it
points at is a **first-publish checklist**, and that is a `RELEASE.md`, not an
agent: attribution sign-off, the version bump and changelog, a rehearsed dry run
against a test registry, and the procedure for withdrawing a bad release.

Write `RELEASE.md` before the first publish. Revisit the seat only if following
it turns out to need judgment rather than care.

---

## requirements-owner: folded into an artifact, may return with a second person

**Trigger: a second contributor.**

Rejected on two grounds. Its "success metrics" remit is often uninstrumentable,
and a second requirements-authoring voice breaks the precedence rule that makes
a document set work: the vision declares itself authoritative on scope and
instructs that `CLAUDE.md` be reconciled to it. A third authority with no stated
ordering would quietly outrank both by being written last.

The missing artifact was `.claude/slice.md`. With one maintainer, requirements
live in the maintainer's head and the vision document, and that is sufficient.
With two contributors it stops being sufficient, because the thing being
coordinated is no longer visible to everyone.

---

## ux-flow-designer: genuinely redundant where practitioner-critic exists

**Trigger: none foreseen. Revisit only if `practitioner-critic` proves
overloaded once real screens exist.**

`practitioner-critic` already carries the full interface-craft mandate.
Splitting the flow work out would separate the judgment about whether a screen
works from the judgment about whether the work gets done, and those are one
judgment in a user's head.

If it ever splits, the defensible cut is **live product** (screens, flows,
state, keyboard) versus **artifact** (the generated document, the export): 
those have genuinely different readers. Not UX versus UAT.

---

## observability-operator: check the remit against the constraints first

**Trigger: depends entirely on the product. Do not adopt by reflex.**

Half the usual remit, metrics, alerting, post-release feedback, describes what
a local-only or privacy-constrained product bans permanently. Naming a seat for
it imports fleet-ops instincts (dashboards, aggregation, a metrics surface) into
a product whose promise may be the opposite.

The legitimate core is usually real and already assigned: structured logging
with correlation ids, an operator-visible event timeline, evidentiary integrity.
Check who owns those before adding a voice.

**What genuinely tends to have no owner** is narrower and belongs to a slice
rather than a seat: the event-code vocabulary, which codes exist, at what
granularity, and what the timeline reads like at minute 49 of a 50-minute run.

---

## The rule these all illustrate

Every entry here failed the bar in the same way: a real concern, correctly
identified, that resolves more cheaply as **an invariant, a test, a hook, a
checklist, or a mode inside an existing agent** than as another voice to route
to and another claim stream to reproduce.

**Reproduction is the constrained resource.** That is the number to watch when
considering any of these.
