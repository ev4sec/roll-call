"""A document that governs a decision must be diffed against reality.

**This is the single highest-value pattern in the engine, and it is the one that
has to be written per project.** The others are portable; this one is a shape.

## The failure it prevents, exactly as it happened

An approval gate decided PROCEED versus APPROVAL REQUIRED by reading the data
model recorded in `CLAUDE.md`. That document had drifted from the code **in both
directions**: six shipped fields were unlisted, and five listed fields had never
been built.

Neither direction is harmless and they fail differently:

* A **shipped-but-unlisted** field makes a genuinely invented field
  indistinguishable from a decided one, so the gate clears it.
* A **listed-but-unbuilt** field lends an undecided idea the authority of a
  recorded contract, so a change that should be argued is waved through as an
  implementation detail.

**The gate did not error. It kept returning confident verdicts from a false
premise**, and several approvals that day rested on "the document already lists
this field". A process whose correctness depends on a document nobody diffs
against the code degrades silently, which is the worst way for a control to
fail.

## The generalization

**Before relying on a file as an input to a decision, ask what would happen if
it were stale. If the answer is "the decision is silently wrong", write this
test.**

Candidates, in rough order of how often they matter:

* the data model or schema recorded in prose
* the licensing and distribution posture against `LICENSE`, `NOTICES`, the
  README and packaging metadata
* the delivery plan against what is actually built
* the invariant register against the tests that claim to prove each entry
* the documented CLI or API surface against the code that implements it
* **a maturity or status document that agents read to decide where to invest**
: the least obvious candidate and, on the project this engine came from, the
  one that drifted twice. Nobody signs it, so nobody diffs it, while the agent
  brief sends every seat there before recommending work. It came to understate
  the codebase by 73%, to deny the existence of a scheduler that had shipped a
  week earlier, and to state two different test totals in two sections with
  nothing reconciling them. **A document nobody signs but everybody reads is
  the most dangerous kind, because being wrong costs a recommendation rather
  than a build error.**

## Four properties that make it work rather than merely exist

1. **It must fail in both directions.** A one-directional check catches the
   easier half and licenses the other.
2. **Every documented-but-unbuilt entry must name the decision authorising the
   gap.** Otherwise "not built yet" becomes an unbounded excuse and the test
   decays into a list of exceptions.
3. **When a new source of truth appears, give it an arm rather than an
   exemption.** This is the one that will actually be tempting, because the
   exemption is a one-line discharge of a failing test and the arm is not. On the
   project this engine came from, a second class of records landed in a separate
   file with its own base, and the test began failing precisely because it was
   working. Adding the new name to the not-checked set would have made the
   *newest* and least-reviewed thing the only one nothing enforces. Widen the set
   the test iterates instead.
4. **Where a document states something that legitimately moves, check the two
   kinds of claim differently, and say which is which.** Some claims are
   decidable and expensive when stale: "there is no scheduler" is either true of
   the tree or not, and a stale one sends someone to build what exists. Check
   those **exactly**, with no tolerance. Others move on every commit: line
   counts, file counts, totals, and a test demanding exactness on those fails
   on work unrelated to the document, which is how a guard gets suppressed
   rather than obeyed. Check those in a **band**.

   **Choose the band against both failure modes and record the arithmetic**, or
   it is an arbitrary number that will be argued with. On the project this engine
   came from the band is 20%: the drift that made the document dangerous was 73%,
   while an ordinary commit moves the total by under 2%. That is an order of
   magnitude above the noise and comfortably below the failure. A band is not a
   license to let the file rot to just inside it; it is the point at which
   staleness stops being cosmetic and starts changing what a seat recommends.

**And check the arm bites before believing it.** Coverage added and never
exercised is worse than none, because it reads as protection: mutate the document
in each direction: delete a shipped entry, invent one the code lacks, and
require a failure each time. That takes a minute and it is the difference between
a guard and a decoration.

---

INSTANTIATION: the test below is a runnable worked example over a Markdown
bullet list. Point `DOCUMENT` and the extractor at this project's real document
and its real source of truth, then delete the skip.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: The prose document that governs a decision.
DOCUMENT = ROOT / "CLAUDE.md"

#: The heading under which the contract is written, exactly as it appears.
SECTION = "## Data model"

#: Entries documented but deliberately not built. Each **must** name the
#: decision that authorised the gap, or this dictionary becomes a list of
#: excuses.
AUTHORISED_GAPS: dict[str, str] = {
    # "Report.output_path": "deferred with the report slice, roadmap.md 2026-08-01",
}


def _documented_entries() -> set[str]:
    """Names the document claims exist, parsed out of the governing section.

    Written against a `- **name**: ...` bullet list because that is the common
    shape. Replace the pattern with whatever this project's document actually
    uses: the parser being specific to the document is the point, not a
    weakness.
    """
    if not DOCUMENT.is_file():
        return set()
    text = DOCUMENT.read_text(encoding="utf-8")
    if SECTION not in text:
        return set()
    body = text.split(SECTION, 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\s*-\s+\*\*([A-Za-z_][\w.]*)\*\*", body, re.MULTILINE))


def _implemented_entries() -> set[str]:
    """Names that actually exist in the code.

    INSTANTIATION: replace with a real reflection of the tree: import the
    models and read their metadata, walk the AST, or query the schema. **Reading
    the code as text is acceptable; reasoning about what it probably says is
    not.**
    """
    return set()


pytestmark = pytest.mark.skip(
    reason=(
        "test_doc_contract is a template. Point DOCUMENT, SECTION and "
        "_implemented_entries() at this project's real contract, then remove "
        "this skip. Leaving it skipped means the highest-value guard in the "
        "engine is not running."
    )
)


def test_the_document_and_the_section_exist() -> None:
    """Negative pole. A renamed heading silently empties every check below."""
    assert DOCUMENT.is_file(), f"{DOCUMENT} is missing"
    assert SECTION in DOCUMENT.read_text(encoding="utf-8"), (
        f"{SECTION!r} is not in {DOCUMENT.name}; the parser would return nothing "
        f"and every assertion below would pass vacuously."
    )


def test_nothing_is_built_that_the_document_does_not_record() -> None:
    """Shipped-but-unlisted: the gate cannot tell invented from decided."""
    undocumented = sorted(_implemented_entries() - _documented_entries())
    assert not undocumented, (
        f"these exist in the code and are not recorded in {DOCUMENT.name}: "
        f"{undocumented}. An approval gate reading that document cannot tell an "
        f"invented one from a decided one, so it clears both."
    )


def test_nothing_is_recorded_that_is_not_built_or_authorised() -> None:
    """Listed-but-unbuilt: an undecided idea wearing the authority of a contract."""
    phantom = sorted(
        _documented_entries() - _implemented_entries() - set(AUTHORISED_GAPS)
    )
    assert not phantom, (
        f"{DOCUMENT.name} records these and they do not exist: {phantom}. Either "
        f"build them, delete the lines, or add each to AUTHORISED_GAPS naming the "
        f"decision that authorised the gap. 'The document listed it' has been used "
        f"as a gate's evidence that a field was intended."
    )


def test_every_authorised_gap_names_its_decision() -> None:
    """Otherwise the exception list is where the contract goes to die."""
    for entry, reason in AUTHORISED_GAPS.items():
        assert len(reason.strip()) > 20, (
            f"{entry} is listed as an authorised gap with no real reason. Name the "
            f"decision and where it was recorded."
        )
