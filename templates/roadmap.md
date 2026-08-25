# Roadmap: deferred work, and what must stay possible for it

**Deferring a feature is not the same as ignoring it.** Some deferred work has a
design consequence *now*, even though nothing is built: a decision made today
can make it cheap, expensive, or impossible later. Those consequences are the
reason this file exists. A list of "things we might do" without them is a wish
list and belongs in an issue tracker.

`commercial-strategist` owns ordering this file by worth, at `required`.
`scope-validator` owns its **must not foreclose** lines, at `advised`. **A
roadmap edit that pulls an item into the current phase is a scope move wearing a
roadmap edit** and goes to `scope-validator` before it lands.

## Deferred

### {{item}}

**Deferred because:** {{reason}}

**Must stay possible:** {{the property a current decision must not destroy, and
what destroying it would cost. Be specific: "do not build the engine such that
the only way a record can exist is 'an adapter returned it'" is actionable;
"keep it flexible" is not.}}

**What would pull it forward:** {{the trigger}}

---

## The honest ceiling

<!-- What the current shape cannot become without changing the vision, said
     plainly. This section exists to be read by the seat most likely to argue
     for exactly that change, and an undefended gap here is how the thing you
     refused gets built with a deal attached. -->

{{What this architecture forecloses, and what a transition would cost.}}
