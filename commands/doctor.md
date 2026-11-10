---
description: Check that roll-call is actually working in this repository. Reports dead routing rules, missing seats, unfilled placeholders, and whether the enforcement hooks have been built.
allowed-tools: Read, Grep, Glob
---

# Check the process

Every guard here is one that fails **silently** when it fails. A routing rule
whose paths no longer exist does not error, it simply never matches. A seat no
rule names is never consulted. A hook that was never built enforces nothing.
In each case the user believes they are covered and they are not, which is the
specific failure this whole process argues against.

So the job is to find guards that are asleep and say so out loud.

Report only what is wrong or unknown. **A healthy setup gets a short answer.**
A report that lists twenty passing checks trains the reader to skim it.

This command reads. It changes nothing, and it does not offer to.

## 1. Is it set up at all

`.claude/routing.toml`, `.claude/operating-procedure.md`, and `.claude/agents/`
must exist, and `CLAUDE.md` must import the procedure with
`@.claude/operating-procedure.md`. If the procedure is not imported, that is
the headline: the session never learns the process, and nothing else matters
until it is fixed. If nothing is there, say roll-call was never set up here
and point at `/roll-call:init`.

## 2. The routing table

Read `.claude/routing.toml` and check each rule. This is the most valuable
section.

- **A rule that matches no file.** Glob each entry in `paths`. A rule with no
  match is a seat nobody will ever be sent to.
- **A rule naming a seat with no file** in `.claude/agents/`. It demands a
  consult that cannot happen.
- **A seat no rule names.** It is decoration.
- **A rule matching a large share of the tree.** It will be muted, and it
  takes the credible rules down with it.
- **A rule aimed at a document by glob.** `**/*.md` never fires; only a rule
  naming the exact file does.
- **An `exclude` that leaves real files covered by no rule.** That is a hole
  wearing a boundary's name.
- **A rule with no `question` or no `why`.**

If every rule is still `advised` long after setup, say so once, without
nagging.

## 3. What the process still does not know

Grep for `{{` under `.claude/` and in `CLAUDE.md`, and count per file. Do not
list every placeholder. Weight them: a missing detail in one seat costs that
seat some precision, while an unfilled vision or an unfilled agent definition
means a seat is ruling from a blank record, which is worse than not asking it.
Name those first.

## 4. Whether anything is enforced

This plugin ships no hooks. Enforcement exists only if it was built in this
repository with the `build-the-engine` skill. Find out which state this is,
and say it plainly, because the two look the same from inside a session.

- **Read `.claude/settings.json`** and list the hook commands it wires.
- **Glob `.claude/hooks/`** and list what is there.
- **Wired and missing:** a command naming a file that does not exist. That
  hook fails on every event, quietly.
- **Present and unwired:** a hook file nothing invokes. Its guard is absent
  and the file sitting there implies otherwise.
- **Neither:** nothing is enforced. Routing is by instruction. Say that this
  is the weak form the operating procedure itself warns about, and name the
  `build-the-engine` skill.

Where hooks are built, check that they are firing, from what they write:

- **`.claude/.consults`** is the consult ledger. Do not read it whole; check
  that it exists and Grep it for each seat's name. An empty ledger in an
  active repository means no seat is being consulted at all.
- **`.claude/.pending-findings`** is the queue of claims waiting for a
  verdict. Count its lines and report the count and the seats. A waiting
  claim is a task for the `reconcile-board` skill, not a finding here.
- **`.claude/.agent-ran`** existing means an agent edited the tree and the
  diff has not been reviewed.

## 5. The tests

Find the project's test directory and check for the four tests the build
guide describes: the routing test, the document contract, the permanent
refusals, and the reachability test. Report which are absent.

If the refusals test is present and its list is empty, it is red on purpose.
A suite that is green **including** that test, with an empty list, has been
made green by deleting a guard, and that is worth saying plainly.

## 6. Output

Group by severity:

- **Broken.** The procedure is not imported, or a wired hook is missing.
- **Asleep.** A guard that exists and can never fire. Usually a dead rule.
- **Unenforced.** What is running on instruction alone.
- **Unknown.** Judgment the process is missing, ordered by which seat it
  disables.
- **Waiting.** Claims in the queue with no verdict.

If everything is healthy, say so in one line and stop.
