# The tests that keep the engine honest

Four test files belong in the project's own test directory. They are
described here, not shipped, and are written in the project's test framework.
Each exists because the thing it checks failed once, quietly, with a green
suite.

Write them after the hooks are proven by hand. A test written against a hook
nobody has watched fire tends to encode what the hook does, not what it
should do.

## 1. The routing table routes

This is the regression anchor for `.claude/routing.toml`. If the table is
edited so that a change which used to summon a seat stops doing so, this test
says so.

It runs against a temporary copy of the repository's real `.claude/` config
with an empty ledger, and calls the router the way the harness does.

Assert all of these:

- **The changes that must route, do.** A list of real paths in this
  repository, each paired with the seat that owns it. Keep the list short and
  real: the data model, the published interface, the security boundary.
- **A fresh consult silences the rule,** and a consult older than the window
  does not.
- **Ordinary files summon nobody.** A test file and a source file no rule
  covers.
- **An advised rule reports and does not block.**
- **Every rule names a seat that exists** in `.claude/agents/`.
- **Every seat has at least one rule.** A seat nothing routes to will never
  be consulted, and reads as coverage it does not provide.
- **Every rule states a question and a cost.** A rule with no question
  produces a survey.
- **The router exits 2 and names who to ask,** run as a real process.
- **A broken routing table fails open:** exit 0 and one line saying so.

The last two need the router to exist. Where the hooks have not been built,
skip those two with a reason that says so, and keep the rest. The rest need
only the table.

## 2. The governing document matches the code

The single highest-value test here, and the only one that cannot be written
in advance, because what it compares is different in every project. The
`write-doc-contract` skill walks through writing it. In short: pick one
section of a document that a gate reads to make a decision, parse that
section from the real file, obtain the same facts from the code, and fail in
both directions with the difference named.

Until it is written, say that it is not, wherever the engine's state is
reported. An install that looks complete with this test missing is hollow.

## 3. The permanent refusals still stand

One seat on the roster is mandated to argue that the vision itself should
change. It can win a refused argument in two moves that no single reviewer
sees as one act: get refused on a citation, then separately propose amending
the cited document. This test breaks that chain.

It holds a list of pairs: a document, and a literal clause that must appear
in it. Each pair is one of the project's permanent refusals, worded closely
enough to the document that a rewrite which guts the meaning also breaks the
match. One clause is usually the right length.

Assert:

- **The list is not empty.** This fails on purpose until the list is filled
  in. A refusals test with no refusals passes vacuously, and a green suite
  that proves nothing is the failure this whole process is built to avoid. If
  the project truly has no permanent refusals, delete this test and the
  passages of the operating procedure that promise it, deliberately.
- **Each governing document exists.**
- **Each clause is still present in its document.** The failure message says
  that if the change was deliberate, the list changes in the same commit with
  the reasoning in the message.

This is not a lock. It makes retiring a refusal a visible act.

If the test hook has been built, have it report this one deliberate failure
as advice, once per session, when it is the only failure. Left as a block it
stops every edit after setup and teaches the reader to approve past blocks.

## 4. The process documents are reachable

A document under `.claude/` either has a path from something guaranteed to be
read, or it does not exist as far as the project is concerned. This was
learned twice: a set of measurement traps filed where no agent was told to
look, and a careful state assessment referenced by nothing.

Three files are guaranteed to be read: `CLAUDE.md`, the operating procedure
it imports, and the agent brief every seat preloads. Assert:

- **All three exist.**
- **Every other Markdown file under `.claude/` is named in at least one of
  them,** or in a file that is. `TEMPLATE-NOTES.md` is the one deliberate
  exception: it is written for a person and nothing should point an agent at
  it.
- **Every agent definition preloads the brief** in its `skills` list.
- **Every agent definition says what it is not for.**
- **The roster the brief describes is the roster that exists.**
- **The routing table parses and is not empty.**
- **The engine config parses,** where it exists.

What this cannot check is whether a document is current. A board can be
reachable, read, and a day out of date. Only updating it at a slice boundary
fixes that, which is what the `reconcile-board` skill is for.
