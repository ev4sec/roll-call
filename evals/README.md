# Evals

`scripts/validate.py` proves the hooks emit the right JSON. Nothing there
proves the model obeys them. These cases do: each one stands up a small
repository, hands the session a prompt, and grades what the session did.

Run them from the plugin root:

```
claude plugin eval . --scaffold --allow-tools Bash Edit Write --max-cost-usd 5
```

`--scaffold` runs each case's `scaffold.sh`, which builds the fixture
repository. The three gated tools are what the cases need: `init` runs the
scaffold script through Bash and writes under `.claude/`, and `seat` edits the
parked-roles register. Each case runs twice by default and once more without
the plugin, so the report shows what the plugin changed.

The runner only grants a shell where it can confine one. On a machine without
its sandbox backend (Windows, as of this writing) it refuses the whole run if
`Bash` is granted, so drop the grant there and the init case fails at its
first step while the other two run:

```
claude plugin eval . --scaffold --allow-tools Edit Write --max-cost-usd 5
```

Three more facts about the eval session, learned by running it. It runs in
don't-ask permission mode, where a write under `.claude/` is denied even with
an `Edit` grant, so the seat case grades the row the session produced rather
than requiring the file to change. The subagent tool may appear as `Task`
rather than `Agent`. And an agent defined in the fixture's `.claude/agents/`
is not loaded into the eval session, so the routed-edit case is graded on
whether the owed consult was acted on in the open (dispatched, substituted
with the seat's question, or declined with a reason), not on which agent
name was spawned.

| Case | What it proves |
| --- | --- |
| `routed-edit-summons-the-seat` | An edit to a routed file is followed by a consult of the owning seat, or an explicit, stated skip. |
| `init-leaves-existing-files-alone` | `/roll-call:init` runs the scaffold script and never writes over an existing `CLAUDE.md`. |
| `seat-parks-a-topic` | `/roll-call:seat` refuses a topic-shaped proposal and records it in `parked-roles.md` with a trigger. |
