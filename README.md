# roll-call

A development engine for Claude Code. It gives you a roster of specialist review
agents, and then it calls the roll. Before a change goes through, the agent that
owns that part of your codebase has to have actually weighed in, and there is a
record proving it did.

That second half is the point. The roster is the easy part.

---

## The problem this solves

You set up subagents. You wrote good instructions about when to use them. You
put a routing table in `CLAUDE.md` saying which agent owns which part of the
codebase.

Then you worked for two hours and consulted none of them.

This is not a discipline problem and it is not fixed by writing the instruction
more forcefully. It is what happens to any rule that lives only in prose: it
gets read at the start of a session and it is gone by the third edit.

Here is the specific failure that produced this project. A session shipped a
database schema change, split two modules, relicensed the project, and altered
the agent roster itself. Every one of those changes was named in the routing
table. Zero agents were consulted. The instruction had been read, and then it
had simply fallen out of the session's attention.

So the rule stopped being a paragraph and became a program.

## How it works

Four moving parts, and each one covers the failure of the one before it.

**1. You describe who owns what.** A small config file maps file paths to the
agent that owns them, along with the question that agent should actually be
asked.

```toml
[[rule]]
paths  = ["src/**/models.py", "src/**/schema.py"]
agents = ["systems-architect"]
level  = "required"
question = """
This changes the data model. State the decision as the thing to build: the
field, its type, whether it is nullable, and what it costs to change later.
"""
```

**2. A watcher records every consult.** When you ask an agent something, that
gets written to a ledger automatically. Not by you remembering to log it. By the
machinery, every time.

**3. When you edit a file, the engine checks the ledger.** If you touched
something a specialist owns and that specialist has not been consulted recently,
you get told so, with the actual question in front of you. On a `required` rule
you cannot quietly move past it.

**4. Claims get checked against reality, not against documents.** The engine
runs the tool rather than reasoning about what the tool probably does. When
packaging config changes, it builds the real distribution and looks inside the
actual bytes. That check exists because on the origin project, a source package
was found shipping the entire private `.claude/` directory, and four agents,
three hooks, and ninety tests had all missed it. One real build settled it in
seconds.

That is the whole idea: **prefer a test to a paragraph.**

## The roster

Nine agents ship with the engine. Each one earns its place by bringing a
distinct *standard of evidence*, not a distinct topic. That distinction is why
nine agents do not collapse into one generic reviewer.

| Agent | The question it owns |
| --- | --- |
| `systems-architect` | Which approach, and what does it cost later? |
| `security-engineer` | Threat-model before it is built; review the diff as it is written. |
| `scope-validator` | Is this the right thing to build, now? Refuses by citing the record. |
| `approval-judge` | Proceed, or does a human need to sign off? |
| `test-strategist` | What would still be broken if every test passed? |
| `practitioner-critic` | Would a real user get their job done, on a bad day? |
| `frontend-architect` | How should this be built in the browser, and what happens at scale? |
| `commercial-strategist` | Is it worth building, and before what else? |
| `content-curator` | Is this true, and may we ship it? |

You are not stuck with these. The routing table names agents by name, so you can
point it at subagents you already have and keep your own roster. The nine are a
reference implementation, not a requirement.

## What else is in the box

**Guards.** Publication is gated by destination rather than by the word "push",
so pushing to a local mirror stays silent and pushing to a public remote does
not. Package uploads are caught separately, because a released version number
can never be reused. Edited files are scanned for the security defects that are
wrong in almost any language. Your test suite runs after edits. Dependency
manifests get audited when they change.

**A document set that agents actually read.** A vision file, an architecture
record, a security invariant register, a lessons file, and a board showing what
is on the bench. These are not documentation. They are the evidence base the
agents reason from, and the engine includes tests that check them against
reality, because a stale document does not throw an error. It returns confident
wrong answers.

**A ledger that keeps score.** Every agent finding is recorded permanently,
including the ones where an agent was confident and wrong. That record is the
point. An agent with no track record is just a second opinion.

## Getting started

Requirements: **Claude Code** and **Python 3.11 or newer**. The engine's
machinery is written in Python. Your project does not have to be.

```
/plugin marketplace add ev4sec/roll-call
/plugin install roll-call@roll-call
```

Restart Claude Code (or run `/reload-plugins`), then, in the project you want
the engine in:

```
/roll-call:init
```

`/roll-call:init` is not optional setup you can skip. It looks at your
repository, works out what it is built with, writes the config and the document
set into your project, and seeds a few routing rules from your actual file
layout. Until it runs, the agents are pointing at files that do not exist yet.

If you install the plugin and forget, roll-call says so once, in the first
session it sees in a repository that has not been set up. Once, and then never
again in that repository, because a plugin installed at user scope is live
everywhere and most directories are not projects you want an engine in.

It will not interrogate you. Anything it can detect, it detects. Anything that
genuinely needs your judgment is left as a clearly marked gap rather than
silently guessed, and `/roll-call:doctor` will keep reminding you which gaps are
still open.

When it finishes, it tells you which file to edit to watch the loop fire for the
first time. That takes about a minute and it is the fastest way to understand
what you just installed.

### What init writes into your repository, and who owns it

This is the part to read before you run it. `/roll-call:init` does not just
configure a plugin. It writes real files into your repository, and **those files
become yours.**

```
your-repo/
  CLAUDE.md                        created, or a section appended if it exists
  .claude/
    engine.toml                    what your project is, for the hooks
    routing.toml                   who owns which paths
    operating-procedure.md         how work moves through the roster
    agent-brief.md                 read first by every agent, every time
    agents/                        the nine seats, as editable markdown
    slice.md                       the board
    vision.md  roadmap.md  architecture.md
    security-invariants.md
    agent-findings.md              the permanent record
    LESSONS.md  parked-roles.md
    repro/README.md                where a reproduction lives
    TEMPLATE-NOTES.md              guidance for filling the above in
  tests/                           four tests that check the engine itself
```

That is 29 files. `TEMPLATE-NOTES.md` is worth a word: the templates ship with
guidance embedded in them about how to fill each one in, and init lifts all of
it into that single file rather than leaving it inline. The reason is cost.
`agent-brief.md` is opened by all nine seats on every round and each agent
definition is loaded on every invocation, so a note left in place would be paid
for on every consult, forever. Nothing loads `TEMPLATE-NOTES.md` automatically.
It is there when you want it.

Three things follow from that, and they are the ones people get surprised by:

**You are meant to edit these.** Especially the agents. A seat that does not
know your domain gives generic advice, and generic advice is what everyone
already has. The nine definitions are a starting point written to be rewritten.
The same goes for `routing.toml`, which only becomes useful once it describes
your codebase instead of our guess at it.

**Updating the plugin will not touch them.** New versions of roll-call ship new
hooks and new templates. They do not reach into your repository and rewrite
files you have edited, because doing that would destroy exactly the work that
makes the engine worth running. The cost of that promise is the other half of
it: improvements to the shipped agents do not reach an existing install either.
You pull those in by hand if you want them, and `/roll-call:doctor` will tell
you when a template has moved on.

**Nothing gets overwritten.** If you already have a `CLAUDE.md`, init appends a
clearly marked section rather than replacing it. If you already have agents in
`.claude/agents/`, init leaves every one of them alone and tells you which of
its own it skipped. Your existing setup wins every collision. If you would
rather point the engine at agents you already wrote, that is a supported
configuration: name them in `routing.toml` and skip the roster entirely.

These files are checked into version control like any other source. That is the
point. The engine's memory of what was decided, what was refused, and which
agent was confident and wrong is only useful if your whole team has it.

### Start advisory

A fresh install does not block anything. Every rule begins as advice, and you
turn on enforcement once the routing table describes your project rather than
our guess about it.

This is deliberate. An alarm that fires on everything gets muted within a day,
and it takes the credible alarms down with it.

## What this runs on your machine

You should know this before installing anything that hooks into your editor.

- **When a file is written**, the engine checks your routing table, scans the
  edited file for security patterns, and may run your test suite. If you changed
  a dependency manifest or packaging config, it may audit dependencies or build
  your package into a temporary directory.
- **Before a shell command runs**, it checks whether that command publishes
  something, and whether an agent has left uncommitted edits in your source that
  you have not looked at.
- **After an agent runs**, it appends a line to the consult ledger.

All of it is Python you can read in `hooks/`. Nothing is minified, obfuscated,
or fetched at runtime. Every hook is launched through `hooks/run.sh`, which
finds a Python 3.11+ interpreter and, when it cannot, says so once and gets out
of the way rather than failing a tool call.

**Nothing is sent anywhere.** The engine makes no network requests. The single
exception is the dependency auditor, which contacts its own vulnerability
database the same way it would if you ran it yourself, and only when you have a
dependency auditor installed and a manifest has changed.

**Nothing is deleted or rewritten behind you.** The engine reads your files,
writes its own ledger, and asks before anything else.

## What this is not

It is not a linter, and it does not replace one. It is not an autonomous agent
that goes off and builds features. It will not make a bad decision good; it will
make sure the decision is put in front of someone qualified to judge it, and
that the judgment is on the record afterward.

It is also opinionated. It encodes a specific belief about how software gets
built well: that expertise should be consulted at the moment a decision is being
made rather than at review time, and that a process which depends on remembering
to follow it is not a process. If you disagree with that, this will feel like
overhead.

## Development

The plugin carries its own suite and an end-to-end validation harness that
stands up real repositories and drives the real hooks:

```
python -m pytest tests/ -q          # 170 tests
python scripts/validate.py          # 35 end-to-end checks
claude plugin validate .            # manifest check
```

## Contributing

Issues and pull requests are welcome. If you are proposing a new agent for the
roster, read `commands/seat.md` first: a seat has to bring a distinct standard
of evidence, not a distinct topic, and that bar applies to the shipped roster
too.

## License

MIT. See `LICENSE`.
