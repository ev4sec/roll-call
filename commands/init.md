---
description: Set up roll-call in this repository. Detects the project, writes the process documents and agent roster into .claude/, and seeds a routing table from the real file layout.
allowed-tools: Read, Grep, Glob
---

# Set up roll-call in this repository

You are standing up a development process in a repository you have not seen
before. Three things matter more than finishing quickly.

**Nothing gets destroyed.** The user did not ask for a merge. An existing file
wins every collision: if the target exists, you do not write it, and you say
so by name.

**Nothing gets guessed into a document that governs a decision.** Roughly
twenty placeholders need judgment you do not have, about who the user is and
what makes this product high stakes. Leave every one of them visible. A
document that is authoritative and wrong is the failure this whole process was
built about, and you would be creating one on your first contact with the
repository.

**Nothing is claimed that is not true.** This plugin ships no hooks. What you
are about to write is the process, the roster, and the routing table. Nothing
you write here enforces a consult. Say that in the report, and name the
`build-the-engine` skill as the way to get enforcement.

## 1. Look before you touch anything

Work it out yourself. Do not interrogate the user.

- **Project name and slug.** From the manifest if there is one, otherwise the
  directory name. The slug is lowercase, hyphen or underscore only.
- **Source root.** Where the product's own code lives, repo-relative. Not the
  repo root unless it truly is.
- **What already exists.** `CLAUDE.md`, anything under `.claude/`, and
  especially `.claude/agents/`. List every file that is already there.

## 2. Tell the user what is about to happen, and get a yes

Report what you detected, then say plainly:

- This writes about 25 files: the documents and the roster under `.claude/`,
  and `CLAUDE.md`. They will appear as uncommitted changes.
- Each write will ask for approval, because this command pre-approves nothing
  but reading. Claude Code treats `.claude/` as a sensitive location, so
  allowing edits for the session does not cover it: expect a prompt per file,
  about 25 in all. Do not try to change their permission settings to avoid
  that.
- There are two ways to do the copying, and it is their choice. You can write
  each file yourself, which needs only edit approval and takes longer. Or you
  can write one short copy script into the repository, show it, run it once
  with their approval, and delete it, which is faster and treats every file
  identically, and is one approval where the other way is about 25. Offer
  both and recommend the script unless they would rather read each file as it
  lands. Do not start a script without asking.
- Name every existing file that will be left alone.
- No hook is installed. Routing will be by instruction until the hooks are
  built.

Wait for confirmation. This is their repository.

## 3. Write the documents

The templates are in `${CLAUDE_PLUGIN_ROOT}/templates/`. For each one: read
it, apply the changes below, and write it to its target **only if the target
does not exist**.

| Template | Target |
|---|---|
| `operating-procedure.md`, `measurement-traps.md`, `agent-findings.md`, `slice.md`, `vision.md`, `roadmap.md`, `architecture.md`, `security-invariants.md`, `LESSONS.md`, `parked-roles.md` | `.claude/` under the same name |
| `agent-brief.md` | `.claude/skills/agent-brief/SKILL.md` |
| `agents/*.md` | `.claude/agents/` under the same name |
| `repro/README.md` | `.claude/repro/README.md` |
| `routing.md` | `.claude/routing.toml`, holding only what is inside the template's `toml` fence |
| `CLAUDE.md` | `CLAUDE.md` at the repository root; see section 4 |

**The same four changes for every file, and no others.** Mechanical work done
slightly differently each time is how two installs end up disagreeing, so do
not improve a template while copying it.

1. **Fill the mechanical placeholders** from what you detected: `{{PROJECT}}`
   and `PROJECT_NAME` become the project name; `{{slug}}`, `{{PROJECT_SLUG}}`,
   `PROJECT_SLUG`, and `project_slug` become the slug. Replace
   `src/project_slug` and `src/PROJECT_SLUG` with the detected source root
   first, before the bare slug, or the path becomes a guess about the layout.
2. **Leave every other `{{...}}` placeholder exactly as it is.** Those are
   the judgment slots.
3. **Restore the frontmatter.** `agent-brief.md` and each agent template open
   with a fenced `yaml` block. In the file you write, that block is the
   frontmatter: put its contents between two `---` lines at the top, with no
   fence.
4. **Lift the installer notes out.** Remove each `<!-- INSTANTIATION: ... -->`
   comment block from the file you write, and collect them, under a heading
   naming the file each came from, into `.claude/TEMPLATE-NOTES.md`. The
   routing table carries its note as a `#` comment block headed
   `INSTANTIATION`; lift that out the same way, since it calls the rules below
   it examples and they will not be. Those notes are written for a person. Left inline they would be read by every
   agent on every consult. Nothing should link to that file.

## 4. `CLAUDE.md` merges; it is the one file that does

- **No `CLAUDE.md`:** write the template, with the four changes applied.
- **A `CLAUDE.md` that already contains `@.claude/operating-procedure.md` or
  `<!-- roll-call:begin -->`:** leave it alone.
- **Any other existing `CLAUDE.md`:** append this section to the end and
  change nothing above it.

```
<!-- roll-call:begin -->
## Operating procedure

This project uses the roll-call process. The standing procedure, the
routing table, and the agent roster live under `.claude/` and belong
to this repository.

@.claude/operating-procedure.md
<!-- roll-call:end -->
```

Skipping the file entirely would leave the procedure unimported and the
process inert, which looks like a working install and is not one.

## 5. Seed the routing table

`.claude/routing.toml` arrives with rules written for a project that is not
this one. Replace them with **two or three rules that match real files here**,
and no more.

Two or three is not modesty, it is the point. A table that fires on every edit
in a busy directory gets muted within a day and takes the credible rules down
with it. Pick the surfaces where being wrong is expensive and hard to reverse:
the data model, a published interface, the security-sensitive path, the
packaging config.

Every rule needs a real question, not a topic. Routing that names an agent
without naming the decision produces a survey, and the process needs a
recommendation stated as the thing to build.

Check each rule's `paths` with Glob before you keep it. A rule that matches no
file is a seat nobody will ever be sent to.

**Set every rule to `level = "advised"`.** The user promotes a rule to
`required` once the table describes their codebase and not your first guess at
it. Delete any rule you did not rewrite.

## 6. Report, and end with one thing to do

Keep it short. Four parts:

1. **What happened.** Files written, files left alone by name, and whether
   `CLAUDE.md` was created, appended to, or untouched.
2. **What is and is not enforced.** The procedure is now imported into every
   session, so the session knows the routing table and the roster. No hook
   exists, so nothing stops an edit that skips a consult. That is the weak
   form, and the procedure itself says so. The `build-the-engine` skill
   builds the hooks in this repository from a specification, one file at a
   time, with the user approving each. The documents refer to four tests
   (routing, document contract, permanent refusals, reachability); init does
   not write those either, and the same skill describes them.
3. **What is still unknown.** How many judgment placeholders remain, where
   they are, and that `/roll-call:doctor` lists them. Name the two or three
   that matter most.
4. **One thing to do next.** Name an actual file covered by a rule you just
   wrote, and the seat that owns it, so the user can ask for that consult and
   see what a seat's answer looks like.

Do not explain the architecture. `CLAUDE.md` now imports the operating
procedure, so from the next message on the session already knows how the
process works and the user can simply ask.
