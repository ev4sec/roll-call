---
name: build-the-engine
description: Build roll-call's enforcement hooks inside this repository, from a written specification, with the user approving every file. Use after /roll-call:init when the user wants routing enforced by a program instead of by instruction, when /roll-call:doctor reports that the hooks have not been built, or when a hook that was built here is misbehaving and needs to be checked against its specification.
---

# Build the engine in this repository

roll-call's whole argument is that a rule kept in prose is read at the start
of a session and gone by the third edit, so the rule has to become a program.
This edition of the plugin ships no programs. The plugin directory accepts
hooks and scripts only from organizations it has verified, and what you have
installed is the part that is allowed: the process, the roster, the routing
table, and this specification.

So the hooks get built here, in the repository that will run them, by you,
with the user reading and approving each file. That is a slower start than a
plugin that arrives with its hooks, and it has one real advantage: every line
that runs on this machine is a line its owner has seen.

**Until this skill has been run, the routing table is enforced by nothing but
the operating procedure.** Say that plainly whenever someone asks what state
the repository is in. A roster that reads as enforced and is not is the exact
failure this project exists to prevent.

## Before you write anything

1. **Confirm init has run.** `.claude/routing.toml` and `.claude/agents/` must
   exist. If they do not, stop and point at `/roll-call:init`.
2. **Ask which language the hooks should be in**, and recommend the one the
   project already uses and already has a test runner for. A hook is ordinary
   project code: it should be reviewed, linted, and tested like the rest. The
   specification in `hooks.md` is language-neutral on purpose.
3. **Tell the user what is about to be written and get a yes.** The list is
   short and fixed: one config file, the hook files under `.claude/hooks/`, a
   wiring block in `.claude/settings.json`, an ignore file for the ledgers,
   and the tests in `tests.md`. Nothing outside those.
4. **Read all three reference files in this skill's directory before the
   first write**: `hooks.md` for what each hook must do, `engine-config.md`
   for the config the hooks read, and `tests.md` for the tests that prove
   them. Writing from memory of an earlier read is how a hook ends up almost
   right.

## The order to build in

Build one hook, prove it, then build the next. A hook that has not been seen
to fire is not a guard yet.

1. **The config.** Write `.claude/engine.toml` from `engine-config.md` and set
   each value from the repository as it is. Switch off what does not apply,
   and say so rather than leaving it on.
2. **The ledger ignore file.** `.claude/.gitignore`, listing `.consults`,
   `.agent-ran`, `.pending-findings`, and `.session/`. These are state local
   to one checkout. If the file exists, add the missing lines and keep the
   rest.
3. **The consult router.** This is the product. If only one hook gets built,
   it is this one.
4. **The agent ledger.** Without it the router can never be satisfied, so
   these two are built as a pair.
5. **The publish guard.**
6. **The post-agent commit guard**, with the snapshot that scopes it.
7. **The rest**, in whatever order the project needs them: the security scan,
   the test runner, the dependency audit, the artifact check, the turn-end
   reminder, the session rebrief, the claim queue.

Stop after step 4 if that is all the user wants. A working router with a
ledger is the engine; everything after it is a second line of defense.

## Wiring

Hooks are wired in `.claude/settings.json`, which belongs to the project and
is checked in. `hooks.md` gives the event and matcher for each hook. Keep to
these rules:

- **One process per event.** Where two hooks share an event, run them from
  one entry point that calls both. Two handlers on one event are two process
  starts on every edit or every shell command, and that cost is what makes
  people switch a guard off.
- **Every handler gets a timeout and a status message.** A hook with no
  timeout inherits a long default and can hang a session on a build that
  never returns.
- **Use the project directory variable the harness provides** for the path to
  each hook. Never a path relative to the current directory, which is
  wherever the last command left it.
- **Check the interpreter exists before wiring it.** If the hooks need a
  runtime the machine does not have, say so and stop. Never install anything
  yourself.
- **If `.claude/settings.json` already exists, add to its `hooks` block and
  touch nothing else in it.** Show the user the merged result before writing.

Hooks register when a session starts. After wiring, tell the user to restart
the session, then prove the router in the new one.

## Proving it

A hook is done when it has been observed doing both of these:

- **Firing when it should.** Edit a file a `required` rule covers and confirm
  the router names the right seat and its question. Run the seat and confirm
  the same edit now passes.
- **Staying silent when it should.** Edit an unrouted file and confirm
  nothing is said. A guard that fires on everything is muted within a day and
  takes the credible guards down with it.

Then write the tests from `tests.md` into the project's test directory and
run them. Each hook's section in `hooks.md` ends with the checks that matter
most for it. Do not report a hook as built on the strength of having written
it.

## What to tell the user at the end

Four things, briefly:

1. Which hooks were built and proven, and which were not built.
2. Which were proven only in one direction, if any, and why.
3. That every routing rule is still `advised`, if init left it that way, and
   that promoting a rule to `required` is what makes the router block.
4. That these files are now the project's own code. A plugin update will
   never change them, which also means a fix to this specification does not
   reach them. `/roll-call:doctor` compares what was built against what is
   wired and reports a hook that is wired and missing, or present and unwired.
