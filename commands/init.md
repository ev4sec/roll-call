---
description: Set up roll-call in this repository. Detects the stack, writes the engine documents and agent roster into .claude/, and seeds a routing table from the real file layout.
allowed-tools: Read, Glob, Grep, Bash, Write, Edit
---

# Set up roll-call in this repository

You are standing up a development engine in a repository you have not seen
before. Two things matter more than finishing quickly.

**Nothing gets destroyed.** The user did not ask for a merge. Existing files
win every collision, and `scaffold.py` enforces that, so do not hand-write
around it.

**Nothing gets guessed into a document that governs a decision.** Roughly twenty
placeholders need judgment you do not have, about who the user is and what makes
this product high stakes. Leave every one of them visible. A document that is
authoritative and wrong is the failure this whole engine was built about, and
you would be creating one on your first contact with the repository.

## 1. Look before you touch anything

Work it out yourself. Do not interrogate the user.

- **Stack.** `pyproject.toml` means python, `package.json` node, `Cargo.toml`
  rust, `go.mod` go, `*.csproj` dotnet. Anything else is `generic`.
- **Project name and slug.** From the manifest if there is one, otherwise the
  directory name. Slug is lowercase, hyphen or underscore only.
- **Source root.** Where the product's own code lives, repo-relative. Not the
  repo root unless it genuinely is.
- **Test directory and command.** What the project already uses. Do not impose
  pytest on a repo that runs `npm test`.
- **Interpreter.** `python3 --version`, falling back to `python` and `py -3`.
  roll-call needs **3.11 or newer**.

If no interpreter of 3.11+ exists, say so plainly and stop. Name what to
install. **Never install anything yourself.** The hooks will be inert until it
is fixed, and a half-set-up engine that looks finished is worse than none.

## 2. Tell the user what is about to happen, and get a yes

Report what you detected, then say plainly: this writes about 27 files into
`.claude/`, `CLAUDE.md`, and the test directory, and they will appear as
uncommitted changes.

Wait for confirmation. This is their repository.

## 3. Run the scaffold

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py" \
  --project-name "<name>" --slug "<slug>" \
  --source-root "<source root>" --test-dir "<test dir>"
```

Add `--dry-run` first if you want to show the user the plan. Read the report:
`written`, `skipped`, `appended`, and the count of judgment placeholders.

## 4. Fill in `engine.toml`

This is the one file the hooks read. Edit `.claude/engine.toml` with what you
detected: `source_root`, the test `command` and `interpreter`, `root_marker`,
and the dependency `manifests` that apply.

Then switch off what does not apply, and say so in the report rather than
leaving it silently on:

- `[artifact] enabled = false` for anything that is not a distributable package.
  That is the right answer for an application.
- Leave `[dependencies] banned` empty unless the project has an actual stated
  constraint a dependency could violate. An empty list is the common answer.

## 5. Seed the routing table

`.claude/routing.toml` ships with rules written for a project that is not this
one. Replace them with **two or three rules that match real files here**, and no
more.

Two or three is not modesty, it is the point. A table that fires on every edit
in a busy directory gets muted within a day and takes the credible rules down
with it. Pick the surfaces where being wrong is expensive and hard to reverse:
the data model, a published interface, the security-sensitive path, the
packaging config.

Every rule needs a real question, not a topic. Routing that names an agent
without naming the decision produces a survey, and the engine needs a
recommendation stated as the thing to build.

**Set every rule to `level = "advised"`.** Nothing blocks on a fresh install.
The user turns on enforcement once the table describes their codebase rather
than your first guess at it. Say this in the report.

Delete any rule you did not rewrite. A rule pointing at paths that do not exist
is dead weight that `doctor` will flag forever.

## 6. Report, and end with one thing to try

Keep it short. Four parts:

1. **What happened.** Files written, files left alone by name, and whether
   `CLAUDE.md` was created or appended to.
2. **What is live.** Which guards are active, and which are off and why.
   "Artifact check is off because this is not a distributable package" is
   useful; silence is not.
3. **What is still unknown.** The judgment placeholder count, where they are,
   and that `/roll-call:doctor` lists them. Name the two or three that matter
   most rather than all of them.
4. **One file to edit.** Name an actual file covered by a rule you just wrote,
   and tell them that editing it will summon the owning agent with its question.

That last line is the sixty seconds where the whole thing clicks. Do not skip it
and do not bury it.

Do not explain the architecture. `CLAUDE.md` now imports the operating
procedure, so from the next message on the session already knows how the engine
works and the user can simply ask.
