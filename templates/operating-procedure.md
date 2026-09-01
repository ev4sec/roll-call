# {{PROJECT}}: Operating Procedure (local, auto-loaded)

Standing procedure for how work is done on {{PROJECT}}. Loaded every session via
an import in `CLAUDE.md`. **This is default behavior, not optional guidance.**
All agents and hooks live under `.claude/` and are local-only: never packaged,
never shipped.

<!-- INSTANTIATION: this document is the engine's constitution. Almost all of it
     is portable and should be kept as written: every section exists because
     something went wrong without it. What must be replaced is marked. What must
     be DECIDED per project:

       * the roster and its cap
       * the surface-routing table's right-hand column
       * what reaches the maintainer
       * the version-control and publishing section, which is deliberately
         per-project and must never be inherited from another project

     Resist trimming the "why" from these sections. A rule with its reason
     removed is a rule that gets argued with and then dropped. -->

## Prime directive: the agents decide, and get verified

Do not resolve hard technical, product, or security questions inline from
memory. Route them to the dedicated review agents. The agents are read-only in
the sense that the primary session is the only thing that writes code: **they
are not advisory in the sense of merely informing a decision the maintainer then
makes.**

**The most qualified agent for a question owns the decision on it.** Ask for a
recommendation stated as the thing to build, not a menu of options to pass
upward. If the answer comes back as a list of choices, that is an incomplete
answer. Send it back and ask which one, and why, with the cost of the
alternative priced.

### Agent consensus IS approval

**Where the owning agent specifies a change and no other agent contradicts it,
that is approval. Build it.** No maintainer round trip, no waiting, no asking
whether to ask. This applies to the data model, interfaces, schemas, format
bumps, dependencies, and the shape of anything technical. `approval-judge` still
runs where it is useful as a *check*, but a PROCEED from it is confirmation
rather than permission, and its absence is not a blocker when the owning agent
has specified the work.

**Concretely: do not write "this is approved and unbuilt" into a resume note.**
That state is a round trip that bought nothing.

**Delegating approval raises the bar on verification, and this is the trade that
makes it safe.** The reason agent output is net-positive is that load-bearing
claims get reproduced before they are acted on. **Approval was never the
control; reproduction was.** Now that consensus carries a change straight into
the code, an unreproduced premise reaches production with nothing between it and
the user. So:

- Reproduce every load-bearing claim before building on it, and say in your own
  reporting which claims you verified yourself.
- **Two agents converging is the strongest signal this setup produces.** Treat
  convergence as a reason to act immediately, not as a reason to relax.
- An agent that flags a claim as `[reasoned]` or `[not run]` has handed you the
  list of things to check first. Ask for that labeling; it is standing.

**What still reaches the maintainer**, and nothing else:

- **The product vision and the non-negotiable constraints.** Scope, priority,
  and anything that changes what the product *is* or retires a constraint. An
  agent may argue a constraint is wrong; it may not retire one, and neither may
  this session.
- **A material conflict between agents** that reproduction does not settle. Two
  agents disagreeing *after both have been checked* is the trigger; one agent
  correcting another is just the process working.

  **One class of conflict is exempted, and the exemption is narrow.** A
  `commercial-strategist` proposal colliding with a `scope-validator` scope
  refusal is **never** settleable by reproduction: one seat's warrant is a
  citation and the other's is a fact about someone outside this repository. Read
  literally, the clause above would send every one of those to the maintainer,
  which is the exact traffic the sprint structure exists to remove. So: **worth
  outranks refusal by default, and the validator's objection is recorded in
  `agent-findings.md` rather than escalated.**

  **It escalates anyway when the objection names a permanent refusal or a
  non-negotiable constraint.** Those live in `tests/test_permanent_refusals.py`
  and in `CLAUDE.md`, so the trigger is checkable rather than a matter of tone.
  The recorded objection is not a formality: it is the artifact that makes a
  wrong default visible in the ledger later, and a default that produced no
  record would be indistinguishable from no default at all.
- **An irreversible publish.** See the version-control section below, which is
  the only home for those rules.
- **A decision whose cost is borne by the user rather than the code.** Route it
  to `practitioner-critic` first; escalate only if that agent and the technical
  agent still disagree, which is the conflict case above.

**Sequencing note.** Design agents run before `approval-judge`, not after: the
judge rules on a concrete proposal, and a proposal is what the design agent
produces. Running the judge on an intention wastes the gate.

**But agents are advisors, not oracles.** On a real project they produce both
findings nobody else would have caught and confident errors. Reproduce a finding
before acting on it when the fix is non-trivial, and say in your own reporting
which claims you verified yourself. **The agents are net-positive because their
output is checked, not because it is trusted.**

Security invariants are registered in `.claude/security-invariants.md`: cite
IDs rather than restating properties from memory.

### A harness instruction is not a project instruction

**This section exists because the whole mechanism was nearly skipped for a
session, and the reason was not laziness.** The primary session was running
under a harness-level instruction that said *"Do not call the AgentTool unless
the user requested it."* That is a sensible default for a generic assistant. It
is the opposite of this project's Prime directive, and it was followed for most
of a day: a blocker was found by measurement, written up as a full proposal with
a priced alternative, and **handed to the maintainer**, who owns vision and
scope, and does not own data-model shape.

The seats then found, in one round, that the proposal was wrong in two ways and
that a constraint inside it was vacuous.

**The rule.** When a harness, a launcher, a system prompt or any instruction
outside this repository conflicts with `routing.toml` or the Prime directive:

1. **Say so, immediately and in the open.** Name the instruction and name the
   rule it contradicts. A conflict resolved silently is indistinguishable from a
   rule that was forgotten.
2. **Do not resolve it by quietly obeying the outside instruction.** The routing
   table is this project's considered position, argued and priced; a harness
   default is a generic one that has never seen this codebase.
3. **Ask once, get a standing answer, and write it into step 3.** One sentence to
   the maintainer is cheaper than a day of unrouted decisions, but **asking every
   session is not cheaper than asking once.**

#### Answer step 3 in writing the first time it is asked

**A rule that resolves to "ask" will stall, and it stalls silently, which is
harder to see than obeying the wrong instruction.** On the project this engine
came from, the same harness line: *"do not call the agent tool unless the user
requested it"*: arrived twice. The first time it was obeyed for most of a day.
The second time it was correctly named in the open, exactly as steps 1 and 2
require, and **the seats still stayed idle for a whole session**, because the
answer arrived at wind-down. Nothing was violated. The mechanism was simply off.

So when the maintainer rules on a recurring outside instruction, **record the
ruling here as a standing answer and delete the asking step for that case.**
Keep step 1: name the conflict when it appears, because a rule followed silently
is indistinguishable from one forgotten. Drop the asking.

**The general form, worth more than the instance:** when a control keeps
producing the right behavior and the wrong outcome, the defect is in the
control's *shape*, not in how convincingly it is argued. A better retelling of
why the rule matters will not fix a step that stalls. Removing the step will.

**The tell to watch for:** *writing a proposal for the maintainer about
something the routing table assigns to a seat.* If a document is being drafted
that explains a technical decision, prices its alternatives, and asks for a
ruling, and `routing.toml` names an owner for that path, then the document is a
consult in the wrong envelope. Send it to the owner.

## "Read-only" describes the agents' role, not their access

Several seats have **Bash**. They can and do write to the working tree: scratch
test files, and *mutations of source files* to check whether a guard fires. That
is legitimate technique; it is how they earn their findings. **But they do not
reliably restore what they changed.**

Verified on the origin project: a review agent removed a field from an integrity
preimage to test whether anything caught it, and left it out. The suite still
passed, because that mutation is precisely the one no test covered. Committing
at that moment would have shipped a tamper-evidence chain that no longer bound
its records together: from a review whose purpose was to *strengthen* that
code.

So, whenever an advisory agent has run:

1. **`git status` and `git diff` before committing.** Not as hygiene, as the
   control that catches this. Reading the diff is what caught it.
2. **Treat an unexpected source change as a mutation left behind**, not as a
   suggestion the agent meant to make. `git checkout --` the file and re-run.
3. **Their scratch test files are findings, not garbage.** Read them before
   deleting, convert what they prove into real tests, then delete the scratch.
4. Prefer launching them when the tree is clean, so any diff is unambiguous.

The `unreviewed_agent_edits` hook, which ships with roll-call, mechanizes step 1.

## Lessons are a deliverable, not a memory

Every session produces at least one thing that would have changed an earlier
decision. If it stays in the transcript it is lost, and the next session pays to
rediscover it. **A lesson that is not written into a file did not happen.**

When something is learned the hard way, route it to exactly one home, in the
same commit as the work that surfaced it:

| What was learned | Where it goes |
|---|---|
| A checkable property of the system | `.claude/security-invariants.md`, as a numbered entry with the measurement in it |
| Something **every** agent should apply | `.claude/agent-brief.md`: every agent reads it first, by instruction |
| A standing instruction for **one** agent | that agent's own `.claude/agents/*.md` |
| An agent claim reproduced, refuted, or acted on unverified | a row in `.claude/agent-findings.md` |
| A constraint or contract for everyone | `CLAUDE.md` |
| A trap that will bite the next session | the resume note in the project memory directory |
| A property worth enforcing mechanically | a test, and then reference the test |

**A rule whose input is a document must test the document.** If the rule you
just wrote depends on a file being accurate, and nothing checks that file
against reality, you have written a wish with extra steps.

This was found the hard way. `approval-judge` decides PROCEED versus APPROVAL
REQUIRED by reading `CLAUDE.md`'s data model, and that document had drifted from
the code **in both directions**: six shipped fields unlisted, five listed
fields never built. Neither direction is harmless and they fail differently: a
shipped-but-unlisted field makes a genuinely invented field indistinguishable
from a decided one, so the gate clears it; a listed-but-unbuilt field lends an
undecided idea the authority of a recorded contract, so a change that should be
argued is waved through as an implementation detail.

**The gate did not error. It kept returning confident verdicts from a false
premise.** A process whose correctness depends on a document nobody diffs
against the code degrades silently, which is the worst way for a control to
fail. Now enforced by a contract test that parses the document and fails on
drift either way, and that requires every documented-but-unbuilt field to name
the decision authorising the gap.

**Generalize it: before relying on a file as an input to a decision, ask what
would happen if it were stale, and if the answer is "the decision is silently
wrong", write the test.**

**Check that the audience actually reads the file you filed it in.** This rule
was broken the day after it was written: measurement traps were recorded in
*this* document, and no agent is instructed to read this document: subagents
get their own definition, not the session's imports. The lesson was filed and
still never arrived.

**A verified finding nobody built is a work queue, not a lesson.** The ledger
records *what was claimed and whether it survived*; it is a track record and it
grows forever. A finding that is reproduced, agreed, and simply not yet built is
a different artifact with a different lifetime: it should be **deleted when it
is discharged**, and until then it should be somewhere a session opens on
purpose. Put it in `.claude/findings-<seat>-<topic>.md`, name it from
`slice.md`, and delete the file when the queue empties.

Prefer a test to a paragraph, and a paragraph to nothing. **An invariant with no
test is a wish; a lesson with no home is a story.**

**Include the measurement, not the conclusion.** "Do not use threads for regex"
is forgettable and gets argued with. "`re` holds the GIL: 6.78s main-thread
stall against a 6.80s match, and counting ticks instead of measuring the gap
gives a false negative that fooled two reviewers" is checkable, reproducible,
and settles the argument before it restarts.

**When an agent is wrong, fix the agent.** A correction that lives only in one
session's chat will be re-litigated by the same agent next month, because its
definition has not changed. Send the correction back *and* edit its definition
if the error was one of method rather than of fact.

## Routing

**`.claude/routing.toml` is authoritative for which seat owns which change.**
The prose here describes each lane and the *judgment* triggers a path glob
cannot express; it is the explanation, not the source of truth. When the two
disagree, the table is right and the prose is stale: say so and fix it.

This split exists because two sources of truth for one question always
eventually disagree, and nothing makes them agree. Two guards make the table and
the roster each other's check: **every rule must name a seat that exists, and
every seat must have a rule**, because an agent the mechanism never invokes is a
roster entry pretending to be coverage.

<!-- INSTANTIATION: one bullet per seat, describing the lane in the project's
     own terms, and naming the distinction against the seat it is most likely to
     be confused with. The distinctions are the valuable part. -->

- Technical and architecture: "which approach and why" → **systems-architect**
- Product fit: "is this the right thing to build" → **scope-validator**
- UX and acceptance: "how should this behave; does the flow survive real
  work" → **practitioner-critic**. Distinct from `scope-validator`: that seat
  asks whether to build the thing, this one assumes it is being built and asks
  whether a real user can get their job done with it. Consult it on anything a
  user sees or reads, **including error messages and CLI output, which exist
  before any GUI does.**
- Security: at design time, on diffs, and in goal mode when a slice closes →
  **security-engineer**
- Coverage: "what would still be broken if every test passed" →
  **test-strategist**
- Frontend: component architecture, state, render behavior at realistic row
  counts, the untrusted-text rendering path → **frontend-architect**. Distinct
  from `practitioner-critic`: that seat rules on whether the screen works for a
  user and wins on any user-visible outcome; this one rules on how it is built.
- Content: authoring and reviewing the project's own domain content, and
  whether its provenance permits shipping it → **content-curator**
- "Does this need the maintainer's sign-off?" → **approval-judge**, which also
  reports **posture drift**.
- "Is this worth building, and before what?" → **commercial-strategist**

## Actually using the agents: the mechanism, not the intention

**This section exists because the prose above did not work.** On the origin
project one session shipped a format bump that moved DDL, split two modules,
relicensed the project and changed the agent roster itself, and consulted **zero
agents**. Every one of those changes is named in the routing table. The table
was read at session start and lost by the third edit. Six well-specified seats
produced no value that day because nothing invoked them.

So routing is **data plus a hook**, and the prose is the explanation rather than
the control:

- **`.claude/routing.toml`**: path globs to owning agents, with the *question
  to ask* and the *cost of skipping* on every rule.
- **The `consult_router` hook**, which ships with roll-call. It fires on every
  write made through the editor tools, matches the path, and exits 2 with the
  agent name and the question when a `required` consult has not happened. A
  file changed by a shell command or a git operation is not a write it is told
  about, so a routed change made that way is yours to route by hand. Fails **open** on a broken table, unlike
  `publish_guard`, which fails closed: an unknown state there might publish;
  here it merely cannot advise, and wedging every edit over a syntax error is
  the worse failure.
- **`.claude/.consults`**: an append-only ledger written by `agent_watch.py`
  when an agent runs. **Not maintained by hand.** A ledger on the honor system
  would fail exactly the way the prose table did.
- **`tests/test_consult_router.py`**: the regression anchor. If the table is
  edited so a previously-routed change stops routing, the test says so.
- **`.claude/engine.toml`**: everything project-specific the hooks need, in one
  place, so the hooks themselves stay portable. If a hook is behaving wrongly,
  check this file before editing the hook.

### When to consult: the parameters

The hook catches *path-shaped* triggers. These are the judgment-shaped ones it
cannot see, and they are yours:

1. **A decision you are about to make twice.** If you are choosing between two
   designs and can argue both, that is the signal. Do not resolve it inline from
   memory. That is the Prime directive, and it is the most commonly skipped
   line in this document.
2. **A first, of anything.** First component, first adapter, first migration,
   first screen. **Design authority has to precede the artifact**; a review
   after the fact inherits the shape it is reviewing.
3. **A number you cannot defend.** A cap, a timeout, a pool size, a threshold. If
   you would not survive being asked "why that value", route it.
4. **Anything a user reads.** Output text, error strings, CLI output, a field
   name that reaches a deliverable. `practitioner-critic` is a *required*
   consult here and this is the clause that gets forgotten.
5. **A claim you are about to write into a document as settled.**

### When NOT to consult: equally load-bearing

Over-consulting is how this mechanism dies. Reproduction is the constrained
resource and every agent answer costs a check.

- **Routine implementation inside an already-approved design.** One design round
  per slice, not per edit. The freshness window exists for exactly this.
- **Mechanical work with a mechanical oracle**: a rename, a call-site sweep, a
  fixture signature change. If the test tells you whether it is right, ship it.
- **A question the register already answers.** Cite the invariant; do not
  re-derive it. Re-asking a settled question wastes the seat and dilutes the
  next answer.
- **When you are the most qualified reader.** The seats exist for domains where
  you are not, which is most of them, but not all of them.

### How to consult efficiently

- **Parallel, in one message, in the background.** Never serially. Two agents
  converging is the strongest signal this setup produces, and you only get it by
  asking both before either answers.
- **Ask for the thing to build, not a menu.**
- **More than four agents owed at once means the change is too broad to route.**
  The hook says so. Narrow it, or run a deliberate full design round.
- **Then reproduce every load-bearing claim.**
- **Skipping is allowed; skipping silently is not.** If a consult is genuinely
  unnecessary, say so in the message and carry on. The hook cannot judge that
  and does not try.

## The roster is capped, and the bar is a standard of evidence

**{{ROSTER_SIZE}} agents.** Adding one more needs an argument that clears this
bar:

**An agent earns a seat only if it brings a distinct standard of evidence, not
a distinct topic, but a distinct way of being right.**

`systems-architect` measures. `security-engineer` exploits.
`practitioner-critic` walks the task and checks the artifact's checkable claims.
`scope-validator` refuses scope. `test-strategist` enumerates failure modes.
`approval-judge` reads the constraint text. `frontend-architect` measures render
behavior at realistic data volumes. `content-curator` traces content to its
source and asks whether it works. `commercial-strategist` prices a thing against
the alternative that would not get built.

**A proposed role graded by "did the check pass" is a hook, not an agent.**

### A seat's tool grant must match the standard of evidence it is asked for

The bar above is a claim about **evidence**, and evidence needs tools. So a grant
that does not match the definition silently converts the seat into a weaker one,
with nothing reporting the downgrade. **Audit the grants against the definitions
whenever the roster changes**, and expect to find mismatches in both directions: 
they fail differently:

- **A missing tool** produces a confident `[reasoned]` answer where a measurement
  was wanted. The seat still replies, at length, and nothing marks the reply as
  degraded. This is the dangerous direction, because the output looks identical.
- **A surplus tool** lets a seat wander into another seat's lane, which is the one
  thing the roster bar exists to prevent.

Three patterns worth checking by name, each found in a real audit:

1. **A seat told to run, holding no way to run.** If a definition says "decode the
   block", "count the offset", "check the arithmetic", or cites a run-the-tool
   invariant, it needs `Bash`. Without it the seat returns `[not run]` on precisely
   the claims that decide a build, and the primary session pays a separate round to
   reproduce each one: spending the reproduction budget the cap exists to protect.
2. **A seat holding a tool its own definition never contemplated.** Definitions
   often enumerate the grant in prose ("you have Read, Grep and Glob"). Where that
   list and the frontmatter disagree, the frontmatter usually drifted, and the prose
   is the considered position.
3. **A web tool on a seat whose whole discipline is local.** Where two seats are
   divided by *direction of appeal*: settleable by citing a file here, versus
   needing a fact about someone outside: a web tool on the local seat is exactly
   the capability that lets it produce the other's output.

**Granting `Bash` more widely is affordable only if the leftover-mutation hazard is
covered.** A review agent with `Bash` will mutate source to see whether a guard
fires, and will not reliably restore it. Seats granted `Bash` for *checking* must be
told in their own definitions not to mutate source, and a hook should put the source
diff in front of the primary session before any post-agent commit.

**A gap worth knowing about:** a path-glob routing table typically has no rule
matching the agent definitions or the routing table itself, so changing the roster: 
or a seat's tools: is unrouted. Whether that should be closed is genuinely
unsettled, because the primary session is the only party that observes a seat
failing, which argues the decision is not routable at all.

**Why the cap is real, not tidiness.** Routing is decided under uncertainty, and
six agents is fifteen pairwise "which one?" boundaries; twelve would be
sixty-six. More importantly, the stated reason this setup is net-positive is
that agent output gets **reproduced before it is acted on**. Reproduction is the
constrained resource. Doubling the producers against a fixed checker does not
double throughput; it makes each check shallower, which is the exact condition
under which a real leak survived four agents, three hooks and ninety tests.

**Two mitigations are mandatory for any seat added late:** it must be **narrowly
triggered** and stay silent outside its domain, and every claim must be labeled
per `agent-brief.md` so the reproduction queue is ordered rather than
exhaustive.

A role that fails the bar is usually better as one of: a numbered invariant, a
hook, a test, a checklist file, or a mode inside an existing agent. **A
recurring check with a mechanical oracle is a test; a question needing judgment
is a seat.**

## The sprint

**The unit of work is one item from the delivery plan.** Not a time box: a
sprint ends when its own **done-when** is met, and the done-when is written
before the sprint opens.

**Why a plan item and not a day.** A time box cuts across the middle of design,
build and review, and the thing it produces is a parked half-state. A plan item
already has a boundary somebody argued about, and the plan contract test already
diffs those items against the tree.

### The four phases, and consults happen in exactly two

**Open.** One parallel design round, membership decided by the surface table
below. Produces the spec the sprint is built against, and the sprint's
done-when. This is the maintainer's only scheduled touchpoint.

**Build.** **Zero consults.** Hooks only. A question that arises here goes to
the blocker ladder, and its destination is a queue file far more often than a
new round.

**Close.** One parallel review round: `security-engineer` on the diff,
`practitioner-critic` on anything a user reads, `test-strategist` on what would
still be broken. Then the fixes it returns.

**Land.** Commit, update the board, delete the sprint's queue file if it
emptied, report. Where packaging changed, build the distribution and read what
is inside it before anything leaves the machine.

**And read the remote build result, because nothing else in this loop does.**
Every hook here fires on a local edit; not one fires after a push. On the project
this engine came from, that produced a measured four-push blind spot: the branch
failed CI continuously while every local check was green, and the handover note
recorded the tree as clean: accurately, because "clean" had quietly come to mean
the local subset. Two causes, and both generalize past that project:

* **The local invocation of a checker is not the CI invocation.** CI ran the type
  checker once per supported platform; the habit locally was to run it once. A
  platform-conditional early return made every following line provably dead on
  two platforms and invisible on the third, which was the author's. Nothing about
  it was a runtime bug. **Run what CI runs**, and where the two genuinely differ,
  say which one "green" refers to.
* **The build command CI uses may not be the one you use.** `python -m build`
  produces the source distribution and then builds the wheel *from that*, so
  anything the sdist omits the wheel omits too. `--wheel` alone builds from the
  working tree and can look perfect while the two-step form ships a broken
  artifact. Generated assets excluded from version control are the usual victim.

One command at Land closes it: check the last run on the branch just pushed.

### The continuation rule

> **Inside an open sprint, do not stop to ask whether to continue. Reach the
> done-when, then report.**

**This exists because it was broken three times in one session.** The maintainer
was asked *"did you fix the failure?"*, *"go for it"* and *"finish them"*. Not
one was a judgment call; all three were continuation decisions, and each cost a
round trip that bought nothing. Meanwhile four scope questions that were
genuinely theirs had sat unanswered for a day. **They were being interrupted
for continuations and not consulted for decisions**, which is the exact inversion
this document exists to prevent.

### Mid-sprint discovery has three destinations, and you choose without asking

| What you found | Where it goes |
|---|---|
| It fixes the thing being built | Do it now, in this sprint |
| Adjacent and cheap, with a mechanical oracle | This sprint's **Close** |
| Needs a design round | Queue file, **next sprint's Open** |

**The failure this prevents, measured.** A one-test flake fix opened three
design rounds *inside a build* and became six commits. Five of six agent
invocations ran sequentially, about **forty minutes of wall time**, when the
whole question was one round's worth of work. The correct handling was: fix the
flake, queue the rest for the next Open, and consult nobody.

### The blocker ladder

Every rung is mechanical except the last. **Do not skip to the bottom**, and do
not stall at the top.

0. **Is it already settled?** `slice.md`'s settled table, the invariant
   register, `agent-findings.md`. Citing beats re-asking, and re-asking a
   settled question dilutes the next answer.
1. **Reproduce before routing.** If the blocker is a claim, measure it. One
   blocker changed shape entirely on measurement, and a sentence about to ship
   turned out to be vacuous in 277 of 277 cases, which no amount of consulting
   would have revealed.
2. **Route by surface, not by topic**, using the table below. Every owner of a
   touched surface goes in the **same parallel round**.
3. **Seats disagree: the surface owner decides**, with the other seat's argument
   attached to the request.
4. **Both hold after reproduction.** A genuine fork, and it is the maintainer's.
5. **No seat owns it.** That is itself the finding: either the roster has a gap,
   proposed against the bar, or the question is the maintainer's.

**Two rules make the ladder terminate rather than stall.** An answer counts as
resolution only if it is **reproduced or names what would falsify it**;
otherwise it is an assumption wearing a verdict. And **a blocker never silently
waits**: if it cannot be resolved inside the sprint, the sprint continues
around it and parks with the blocker named, rather than the whole sprint
stopping on one question.

### Route by surface, because routing by topic is what failed

**Before asking "what is this about", enumerate what it touches.** A question
was once routed as a semantics question to two technical seats; it was also an
**operator-visible string**, so `practitioner-critic` belonged in the same round
and instead arrived two rounds later and sent the design back.

<!-- INSTANTIATION: the left column is the project's real surfaces. Write them
     from the tree, not from a template. -->

| Surface the change touches | Owner |
|---|---|
| A stored field, a format, a public interface | `systems-architect` |
| Anything a user **reads** | `practitioner-critic` |
| A number that reaches a deliverable | `practitioner-critic`, and `systems-architect` if computed |
| Untrusted input, egress, secrets, a dependency | `security-engineer` |
| The project's own domain content | `content-curator` |
| A screen, a component, render behavior at volume | `frontend-architect` |
| Whether it should exist, answerable by citing a file here | `scope-validator` |
| Whether it is worth building first, needing an outside fact | `commercial-strategist` |
| A declaration site against recorded intent | `approval-judge` |
| A new module whose tests are unwritten | `test-strategist` |

A change touching two surfaces has two owners and **both go in round one**. More
than four owed at once means the sprint is too broad.

### The one boundary that is not topical

`scope-validator` and `commercial-strategist` can be handed the same sentence.
**They divide by direction of appeal**, and the test decides a case:

- **Settleable by citing a file in this repository?** The validator. It refuses
  by pointing, and *there is no clause in its definition that produces a
  capability*. It cannot originate, only refuse.
- **Needs a fact about someone outside this repository?** The strategist.
- **Requires one of those files to change?** The maintainer. The strategist
  drafts the proposal he rules on.

Neither seat can produce the other's output.

### The two-move hazard, and the three mechanisms against it

A seat mandated to argue the vision should change can win a refused argument in
two moves that no single reviewer sees as one act: propose a capability, get
refused on a citation, separately propose amending the cited document on
commercial merit, then re-propose the capability into a record that no longer
refuses it. **Nobody is overruled and nobody sees a coupled act.**

The origin project shipped this class of failure once already: a license file
contradicted the recorded business intent for four days, past six agents, three
hooks and 978 tests, *because nothing read one against the other.*

1. **An amendment proposal must enumerate every refusal it would unblock.** Not
   "should". Incomplete without the list, and sent back the way an options menu
   is sent back. The amendment and the thing it enables get read together, in
   one document, by the person ruling.
2. **`scope-validator` is a required co-consult on any such amendment, with no
   veto**, producing that list independently. Two lists that agree cost a
   paragraph; two that disagree is a material conflict for the maintainer. It
   must not become a veto: a gate that only ever ratifies is a gate nobody
   reads.
3. **The permanent refusals are asserted as literal strings** by
   `tests/test_permanent_refusals.py`. Deleting one is a failing test rather
   than a diff nobody reads, so retiring it becomes a deliberate act with a name
   on it.

**And the asymmetry that makes all three necessary.** Every other seat's claims
are checkable against a file on this machine; the strategist's are checkable
only against the outside world, and reproduction against a local oracle is this
project's single strongest control. So **a commercial claim that would retire a
refusal carries a citable external source or a named prospect, never a
recollection.**

### What reaches the maintainer, and when

**At Open, and only if the ladder failed.** He sees the sprint's goal, its
done-when, and any question that reached rung 4 or 5. **Silence means the ladder
resolved everything**, which is the intended state.

At Land he reads the close report and the refreshed board. Neither is a request
for a decision.

## Feature / change loop

The phases above supersede this list; it is kept because the numbered steps are
referenced by name and because the detail in steps 1, 8 and 9 is still operative
inside the phases.

1. **Design**: consult, in parallel and only where the change actually touches
   their lane.

   **`practitioner-critic` is a required consult**, not optional, not from
   memory: whenever the change touches a screen, a flow, an error message, an
   output layout, or **a field name a user will read.** That last clause is the
   expensive one: acceptance criteria become columns, and a field discovered
   missing after the schema ships is a migration plus a re-interpretation of
   historical data.

   One design round per slice, not per edit.
2. **Gate**: before touching the data model, a public interface, a
   non-negotiable constraint, dependencies, or scope, run `approval-judge`. If
   it returns APPROVAL REQUIRED, stop and ask.
3. **Implement**: primary session only.
4. **Auto-checks**: on write, deterministic hooks fire. Address what they
   surface before moving on.
5. **Review**: run `security-engineer` in review mode on the diff for
   non-trivial code.
6. **Verify the artifact, not just the source**: before any publish, and after
   any change to packaging config, build the distribution and read what is
   actually inside it.
7. **Proceed** only if green and no approval tripwire; otherwise escalate.
8. **The delivery plan governs and is adhered to rather than consulted.** It
   carries the gates, the refusals, the foreclosures, and the questions that are
   the maintainer's. A contract test diffs it against the tree in both
   directions, because **a plan with no oracle is a wish.** The refusals are the
   most deletable part of that document and the most valuable, so they are
   asserted by name.
9. **Update `.claude/slice.md` when the slice moves**, before parking the work.
   Not as bookkeeping: it is the first file every agent opens, and the consult
   router drives all of them hard, so **a stale slice file is a wrong map
   multiplied across the roster.** It was stale for a day on the origin project,
   listing three shipped subsystems as upcoming, and no test can catch that.
   `tests/test_process_docs.py` proves the file is *reachable*; only this step
   keeps it *true*.

   The trigger is a slice boundary or a wind-down checkpoint, not every commit.
   What must be right: what is built, what is next in order, and any question
   the slice settled so nobody pays to ask it twice.

   **At the same trigger, `commercial-strategist` reports vision drift.** This
   is a procedure line and not a routing rule, deliberately: the duty is
   *periodic*, and the router fires on paths, so no glob can express "36 commits
   have landed since this file moved."

## Why step 5 is not the same agent answering twice

Measured on the origin project. `security-engineer` threat-modelled a change
before it existed and specified three requirements. The primary session built
exactly that. The **same agent**, run again in review mode on the diff, returned
`fix-before-merge` with two HIGH defects **in code written to its own
specification**:

- a response the interface permits was unstorable, and the failure destroyed the
  record that was the evidence of it;
- the vocabularies it had asked to be constrained were hand-copied into the
  constraint with nothing joining them to their source.

Neither is a specification defect. Both are *implementation* defects that the
specification could not have prevented, because **a specification describes the
end state and a diff shows what was actually done to reach it.** The design pass
asks "what should exist"; the review pass asks "what does this code do at the
edges the design did not enumerate".

**So do not skip step 5 on the grounds that the design agent already ruled.** The
temptation is strongest exactly when the design was good, because the build
feels like transcription. It is not.

**Ask for the review as a diff review, and tell it what you built.** Listing the
specification points you believe you satisfied is what lets the agent check
rather than re-derive, and it is also what surfaces the corner you cut. **A cut
corner named in the request gets a decision; one left unmentioned gets found or
does not.**

## Why step 6 exists

Steps 1 to 5 all read *source*. A distribution was found shipping the entire
`.claude/` directory: every agent definition, every hook, every internal
document, and four agents, three hooks and ninety tests all missed it, because
`.git/info/exclude` keeps those paths out of git while the build backend honors
only `.gitignore`. A security review had reasoned it was not a live leak. One
`python -m build` settled it.

The generalization: **when a claim is about what a tool does, run the tool.**

## Version control and publishing

<!-- INSTANTIATION: THIS SECTION IS DELIBERATELY PER-PROJECT AND MUST NOT BE
     INHERITED. What counts as publishing, what the blast radius is, and what a
     brief must contain differ per project, and a single global rule would apply
     one project's answer to another. Write this project's own version, and make
     `publish_guard.py` and `[publish]` in engine.toml agree with it.

     The shape below is the origin project's and is a reasonable default for
     anything with a public package. Adjust or replace entirely. -->

**Local commits do not need permission.** Commit as work progresses, at sensible
boundaries, with clear messages. A local commit is private and reversible, so
asking about each one costs time and protects nothing.

**Publishing does need permission**, and needs more than a yes/no prompt. Before
anything leaves the machine, write a **manager-level review brief** and wait for
an explicit go-ahead:

- One to two paragraphs. High level.
- What is being published and why it matters, in product or business terms.
- Risk and blast radius, who is affected if this is wrong, and how reversible
  it is.
- What was actually verified, stated plainly, including what was *not* checked.

No file lists, no commit-by-commit walkthrough, no diff summary. This is a
decision aid for "should this go out", not a code review.

Be honest in the brief about anything shaky. **A brief that oversells is worse
than no brief, because it is the artifact the publish decision rests on.**

**Present the brief; do not announce that one is needed.** Saying "publishing
needs a brief and your go-ahead" is a stall. It hands back the very thing the
session was about to write. When unpushed work reaches a natural boundary, write
the brief in full and **carry on with the next task while he decides.**

**Re-brief when the facts move.** A brief is a snapshot of risk. If work
continues after it is presented and changes something it asserted, present a
revised brief rather than letting the decision rest on a stale one.

`publish_guard.py` enforces the pause and fails closed on unparseable input, but
honor the intent regardless of whether the hook is active: **the hook can only
stop the command, and the brief is not automatable.**

## Hard rules (always)

- Commit freely. Local commits need no permission.
- **Agent consensus is approval.** Where the owning agent specifies a change and
  no other agent contradicts it, build it. Reproduce the load-bearing claims
  first; that is the control, and it is the only one.
- Propose before changing the data model, a public interface, or a published
  schema: **to the owning agent.** Its specification is the approval;
  `approval-judge` is a check you may run, not a gate you must clear. Nothing
  here is built unproposed. Only the reader changed.
- Never add a dependency without saying why in the same message.
- Keep all process machinery local to `.claude/`; never let it enter a package.

## Reload note

Agents and hooks register at session start; after editing them, relaunch to
activate.
