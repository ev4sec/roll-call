# roll-call

A development process for Claude Code. It gives you a roster of specialist
review agents and a table saying which agent owns which part of your codebase,
and then it holds you to it: before a change goes through, the agent that owns
it has to have actually weighed in, and there is a record proving it did.

**This edition contains instructions only.** It ships no hooks, no scripts,
and nothing that runs by itself. It sets the process up in your repository,
and it carries a written specification for the enforcement hooks, which
Claude builds inside your repository, one file at a time, with you approving
each. The section "What this edition is" below says why, and what that costs.

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

**2. A ledger records every consult.** When an agent you asked finishes, that
gets written down. Not by you remembering to log it. By a hook, every time.

**3. When you edit a file, a router checks the ledger.** If you touched
something a specialist owns and that specialist has not been consulted
recently, you get told so, with the actual question in front of you. On a
`required` rule you cannot quietly move past it.

**4. Claims get checked against reality, not against documents.** Run the tool
instead of reasoning about what the tool probably does. On the origin project,
a source package was found shipping the entire private `.claude/` directory,
and four agents, three hooks, and ninety tests had all missed it. One real
build settled it in seconds.

That is the whole idea: **prefer a test to a paragraph.**

## What this edition is

Parts 2 and 3 above are programs, and this plugin does not contain them.

The plugin directory accepts hooks, scripts, and broad tool permissions only
from organizations it has verified. roll-call's author is not one, and there
is currently no way to apply. So the edition the directory lists is the part
that rule allows: Markdown.

What you get from it:

- **`/roll-call:init`** writes the process documents, the nine-seat roster,
  and a routing table seeded from your real file layout into your repository.
- **`/roll-call:doctor`** reads your setup back and says what is asleep: a
  rule that matches no file, a seat nothing routes to, a document still full
  of placeholders, a hook that is wired and missing.
- **`/roll-call:seat`** judges a proposed new agent against the bar the
  roster is held to, and records why when the answer is no.
- **Five skills**, loaded when the work calls for them: writing a routing rule
  that survives a busy week, writing a test that diffs a governing document
  against the code, reconciling the board with the repository, finding the
  gap in the roster nobody proposed, and building the engine.

That last skill, `build-the-engine`, is the answer to the missing programs. It
holds a specification for each hook: what it reads, what it decides, what it
prints, and which way it fails, including the behaviors that were only found
by running them. Claude writes the hooks from it into your repository's own
`.claude/hooks/`, in your project's language, and you approve every file.

**Be clear-eyed about the state in between.** After init and before the hooks
are built, the routing table is followed on instruction. That is the
arrangement the first section of this README says does not work. The process
documents say so too, and `/roll-call:doctor` reports which state a repository
is in, because a roster that reads as enforced and is not is the failure this
project exists to prevent.

### The trade

Building the hooks in your own repository is slower than installing a plugin
that arrives with them, and it has two real costs. The hooks are written
fresh each time, so they are only as good as the specification and your review
of them. And a fix to the specification does not reach hooks that were already
built.

It has one real advantage: every line that runs on your machine is a line you
have read, in a file you own, in your version control.

### The full engine

The original engine, with its hooks, scripts, and test suite already written,
is a separate plugin in a separate repository:
`github.com/ev4sec/roll-call-engine`. The plugin directory has not reviewed
it and does not list it. Everything through version 0.6.3 of this repository
is that engine, and its history and tags remain here.

If you installed roll-call directly from this repository before version
0.7.0, read the 0.7.0 entry in `CHANGELOG.md` before you update.

## The roster

Nine agent definitions come with the process. Each one earns its place by
bringing a distinct *standard of evidence*, not a distinct topic. That
distinction is why nine agents do not collapse into one generic reviewer.

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

You are not stuck with these. The routing table names agents by name, so you
can point it at subagents you already have and keep your own roster. The nine
are a reference, not a requirement.

## Getting started

Requirements: **Claude Code**. Nothing else is needed to set the process up.
The hooks, if you build them, need whatever runtime you choose to write them
in.

Install roll-call from the plugin directory, or straight from this repository:

```
/plugin install roll-call --marketplace ev4sec/roll-call
```

Then, in the project you want the process in:

```
/roll-call:init
```

It looks at your repository, tells you what it is about to write, and waits
for a yes. It will not interrogate you. Anything it can detect, it detects.
Anything that needs your judgment is left as a clearly marked gap, and
`/roll-call:doctor` will keep telling you which gaps are still open.

Because this plugin pre-approves nothing but reading, every file init writes
asks for your approval. Claude Code treats `.claude/` as a sensitive location,
so that is a prompt per file, about 25 in all, even with edits allowed for the
session. If you would rather decide once, init will offer to do the copying
with one short script that it shows you, runs with your approval, and deletes.

When you want routing enforced by a program, ask Claude to build the engine.
The router and the consult ledger are the two hooks that matter; the rest are
a second line of defense and can wait.

### What init writes into your repository, and who owns it

`/roll-call:init` writes real files into your repository, and **those files
become yours.**

```
your-repo/
  CLAUDE.md                        created, or a section appended if it exists
  .claude/
    routing.toml                   who owns which paths
    operating-procedure.md         how work moves through the roster
    skills/agent-brief/SKILL.md    preloaded into every seat, every time
    agents/                        the nine seats, as editable Markdown
    slice.md                       the board
    vision.md  roadmap.md  architecture.md
    security-invariants.md
    agent-findings.md              the permanent record
    LESSONS.md  parked-roles.md
    measurement-traps.md
    repro/README.md                where a reproduction lives
    TEMPLATE-NOTES.md              guidance for filling the above in
```

`TEMPLATE-NOTES.md` is worth a word. The templates carry guidance about how to
fill each one in, and init lifts all of it into that single file. The reason
is cost: the brief is loaded into all nine seats on every round and each agent
definition is loaded on every invocation, so a note left in place would be
paid for on every consult. Nothing loads `TEMPLATE-NOTES.md` automatically.

Three things follow, and they are the ones people get surprised by:

**You are meant to edit these.** Especially the agents. A seat that does not
know your domain gives generic advice, and generic advice is what everyone
already has. The same goes for `routing.toml`, which only becomes useful once
it describes your codebase and not a first guess at it.

**Updating the plugin will not touch them.** New versions do not reach into
your repository and rewrite files you have edited. The cost of that promise is
the other half of it: improvements to the templates do not reach an existing
install either.

**Nothing gets overwritten.** If you already have a `CLAUDE.md`, init appends
a clearly marked section and changes nothing above it. If you already have
agents in `.claude/agents/`, init leaves every one of them alone and tells you
which of its own it skipped. Your existing setup wins every collision.

These files are checked into version control like any other source. The
record of what was decided, what was refused, and which agent was confident
and wrong is only useful if your whole team has it.

### Start advisory

Every rule begins as advice. You promote a rule to `required` once the routing
table describes your project. An alarm that fires on everything gets muted
within a day, and it takes the credible alarms down with it.

## What this runs on your machine

Nothing, by itself.

- **The plugin has no hooks.** Nothing in it runs on an event, in the
  background, or at session start.
- **Its commands and skills pre-approve only reading**: the Read, Grep, and
  Glob tools. Every file write and every shell command Claude proposes while
  following them asks you first, under your own permission settings.
- **It contains no executable files.** Every file is Markdown or JSON, plus
  one PNG icon.
- **It fetches nothing.** No instruction in it downloads code.

If you ask Claude to build the hooks, those hooks will run on your machine,
on edits and shell commands in that repository. They are files in your
repository that you approved one at a time, wired in a settings file you can
read, and removing that wiring switches them off.

## What this is not

It is not a linter, and it does not replace one. It is not an autonomous agent
that goes off and builds features. It will not make a bad decision good; it
will make sure the decision is put in front of someone qualified to judge it,
and that the judgment is on the record afterward.

It is also opinionated. It encodes a specific belief about how software gets
built well: that expertise should be consulted at the moment a decision is
being made, not at review time, and that a process which depends on
remembering to follow it is not a process. If you disagree with that, this
will feel like overhead.

## Contributing

Issues and pull requests are welcome. If you are proposing a new agent for the
roster, read `commands/seat.md` first: a seat has to bring a distinct standard
of evidence, not a distinct topic. Changes to the hook specification in
`skills/build-the-engine/` should say what was observed that the specification
got wrong.

Pull requests to this repository may contain only Markdown, JSON, and images.
Code belongs in the engine repository.

## License

MIT. See `LICENSE`.
