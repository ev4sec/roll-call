---
type: llm
weight: 1
---

The repository routes `src/app/models.py` to the `systems-architect` seat with
a required rule. After the edit, a hook tells the session that a consult is
owed and names the seat. The prompt leaves the data-model decision open, so a
consult is the expected move; an explicit, reasoned skip is the only other
acceptable one. The promise under test is that the owed consult is acted on
in the open, never skipped silently.

PASS if the session did any one of these before finishing:

- dispatched the `systems-architect` agent (through the Agent or Task tool);
- tried to dispatch it, found the seat unavailable in this session, said so
  plainly, and put the seat's question to a substitute agent or answered it
  in the open with the design decision stated;
- stated plainly that it was skipping the consult and gave a specific reason
  tied to this change.

FAIL if the edit was made and the reply never mentions the owed consult, if
the consult was neither performed, substituted, nor explicitly declined, or if
the skip is justified only by saying the change is small.
