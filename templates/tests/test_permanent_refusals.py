"""The refusals that must survive a persuasive argument.

**Why a test and not a paragraph.** One seat on this roster is mandated to argue
that the vision itself should change, and it can win a refused argument in two
moves that no single reviewer sees as one act: propose a capability, get refused
on a citation, separately propose amending the cited document on commercial
merit, then re-propose the capability into a record that no longer refuses it.
Nobody is overruled and nobody sees a coupled act.

Asserting the refusals as **literal strings** breaks that chain at step two.
Deleting a refusal becomes a failing test with a name on it rather than a diff
nobody reads, which makes retiring one a deliberate act.

**This is not a lock.** A refusal can be retired: change the document and change
this list, in the same commit, with the reasoning in the message. The test does
not prevent the change; it prevents the change from being invisible.

The same control shape guards the data model and the licensing posture. All
three exist because **a document that governs a decision, and that nothing diffs
against reality, degrades silently.**

---

INSTANTIATION: fill in `REFUSALS`. Each entry is a substring that must appear
somewhere in the named document, worded closely enough to the document that a
rewrite which guts the meaning also breaks the match. Too short and it matches
by accident; too long and every copy-edit is a failing test. One clause is
usually right.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: (document, literal substring that must survive). The document is
#: repo-relative.
REFUSALS: list[tuple[str, str]] = [
    # (".claude/vision.md", "no telemetry of any kind"),
    # ("CLAUDE.md", "Client data never leaves the machine"),
    # (".claude/roadmap.md", "is a separate product with a separate name"),
]

#: Documents that must exist for the refusals to be assertable at all.
GOVERNING_DOCUMENTS = ("CLAUDE.md", ".claude/vision.md")


def test_the_refusal_list_has_been_filled_in() -> None:
    """A permanent-refusals test with no refusals is theatre.

    This fails loudly on a fresh instantiation rather than passing vacuously,
    because a green suite that proves nothing is the failure mode this whole
    engine is built to avoid.
    """
    assert REFUSALS, (
        "REFUSALS is empty. Either fill it with this project's permanent "
        "refusals: the things that must survive a persuasive commercial "
        "argument, or delete this file and the sections of "
        ".claude/operating-procedure.md and .claude/agents/commercial-strategist.md "
        "that promise it exists. A guard that asserts nothing is worse than no "
        "guard, because the roster reads as covered."
    )


@pytest.mark.parametrize("relative", GOVERNING_DOCUMENTS)
def test_the_governing_documents_exist(relative: str) -> None:
    """Negative pole: a renamed document would make every check below vacuous."""
    assert (ROOT / relative).is_file(), f"{relative} is missing"


@pytest.mark.parametrize(
    ("document", "refusal"),
    REFUSALS,
    ids=[f"{d}:{r[:40]}" for d, r in REFUSALS] or None,
)
def test_the_refusal_still_stands(document: str, refusal: str) -> None:
    path = ROOT / document
    assert path.is_file(), f"{document} is missing entirely"
    text = path.read_text(encoding="utf-8")
    assert refusal in text, (
        f"{document} no longer contains the refusal {refusal!r}.\n\n"
        f"If this was deliberate, change this test in the same commit and say in "
        f"the message which argument retired it and who ruled. If it was not, "
        f"something rewrote a permanent refusal without anybody deciding to."
    )
