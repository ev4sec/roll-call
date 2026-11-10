# What each hook must do

This is a specification, not source code. It says what each hook reads, what
it decides, what it prints, and which way it fails. Write the hooks in the
project's own language and keep them under `.claude/hooks/`.

Every statement about the harness below was learned by running it. Where a
behavior is marked **measured**, it is not in the documentation and was found
the hard way; do not "simplify" it away.

## Rules every hook follows

- **Read the payload from standard input as JSON.** Read it once.
- **Find the repository from the project directory the harness provides in
  the environment.** Never from the hook's own location and never from the
  current directory. A hook that resolves the wrong root does not fail; it
  reports confidently about a tree nobody asked about.
- **Do nothing unless `.claude/engine.toml` exists, and do nothing if
  `.claude/.roll-call-ignore` exists.** Check both before any other work.
- **Never crash the session.** Malformed input, a missing file, and an
  unreadable config all end in a clean exit. Each hook states below whether
  that exit is silent or a prompt.
- **Be silent on success.** A hook that reports twenty passing checks trains
  the reader to skim the one that matters.
- **Collapse a repeat, never silence it.** When the same advisory would print
  again in one session, print one line that still says the condition holds.
  A warning suppressed completely makes "still broken" look like "clean".
- **Keep session state apart from the ledgers.** Memory that belongs to one
  session, such as which messages were already shown in full, goes in
  `.claude/.session/`, one file per session id, ignored by version control
  and aged out after two days. With no session id in the payload, or a
  directory that cannot be written, keep no state and say the full thing
  every time.

## The consult router

**Event:** after a file is written through an editor tool (Write, Edit, or
NotebookEdit).

**Reads:** the edited path from the tool input; `.claude/routing.toml`;
`.claude/.consults`.

**Decides:**

1. Make the path repository-relative with forward slashes. An edit outside
   the repository matches nothing.
2. Find the rules whose `paths` match. A pattern ending in `/**` matches
   everything under that directory. A `*` matches across directory
   separators.
3. Paths ending in `.md`, `.txt`, or `.lock` match no pattern at all, with
   one exception: a rule that names that exact file fires. `**/*.md` stays
   silent; `.claude/slice.md` written into a rule is a deliberate act and is
   honored. Compare case-insensitively and ignore a leading `./`.
4. Drop any rule whose `exclude` patterns match the path.
5. For each remaining rule, find the agents with no entry in the ledger
   newer than `fresh_hours` (default 24). Those are owed.
6. Split the rules still owing into `required` and `advised`.

**Says:**

- **Required and owed:** print to standard error and **exit 2**. Exit 2 is
  what makes the message reach the session as feedback instead of scrolling
  past. The message names the file, each owed agent, and each rule's `why`
  and `question`. Then it tells the session to launch the agents in parallel
  in one message, ask for a recommendation stated as the thing to build, and
  reproduce every load-bearing claim before acting. It ends by saying that a
  consult that is truly not needed must be skipped out loud, never silently.
- **More agents owed than `max_parallel` (default 4):** say the change is too
  broad to route and should be narrowed or taken to a deliberate design
  round. Never drop this line when shortening a repeat.
- **A repeat in the same session:** the full text once per rule per session;
  after that one line naming the agents and rule ids and pointing at the
  routing table. It still exits 2 every time.
- **Advised and owed:** one line, once per session, exit 0.

**Fails open.** A missing or unparseable routing table prints one line to
standard error and exits 0. Wedging every edit in the repository over a
syntax error is the worse failure.

**It does not block the write.** It runs after the edit. The point is that
the omission is visible and repeated, which is the difference between a rule
and a wish. It never claims what an agent said, only whether one was asked.

**Check:** a required rule blocks; a fresh ledger entry clears it; a stale
entry does not; an unrouted file is silent; a broken table exits 0.

## The agent ledger

**Event:** when a subagent finishes. **Measured:** not on the tool call that
launches it. Subagents run in the background, so that call returns at launch,
before the agent has done anything. A ledger stamped there credits a consult
that has not been answered.

**Reads:** the agent's name and id from the payload.

**Does:** appends one line, `<agent name>` then a tab then the Unix time in
seconds, to `.claude/.consults`. Append only. Never rewrite or clear it; the
router reads recent entries from the end.

**Why a hook writes it.** A ledger kept by remembering fails exactly the way
a prose routing table fails.

Silent, never blocks.

## The post-agent commit guard

Review agents with shell access change source to test whether a guard fires,
and do not reliably put it back. One such change reached a commit on the
project this came from. This guard puts the diff in front of the person
before the commit.

It has three parts.

**When a subagent starts:** record a fingerprint of every file under the
configured source root that differs from the last commit, plus untracked
files, keyed by the agent id. Store it under `.claude/.session/`.

**When that subagent finishes:** take the fingerprints again, compare, and
append a line to `.claude/.agent-ran` with the time, the agent name, and the
files that changed while it ran. Write a single `-` in place of the list when
the comparison ran and nothing changed. Leave the list off entirely when the
comparison could not run.

**Before a shell command runs:** if the command is a `git commit` and the
marker file exists, read the marker, delete it, and show the diff of the
named files as a confirmation prompt. When any agent's changes are unknown,
show the whole source root's diff. When nothing under the source root
changed, say nothing.

Details that were each a real defect once:

- **`commit` must be the git subcommand**, found by skipping git's global
  options and their values. Matching the word anywhere fires on a search for
  the word "commit", and firing deletes the marker, so a read-only command
  spends the one prompt the real commit needed.
- **Cap the diff** at about 120 lines and say how many more there are.
- **One prompt per agent run**, not per commit. Firing on every commit is
  ignored within a day.

**Says:** a confirmation prompt, by returning the pre-tool decision "ask"
with the diff as the reason. It never approves and never refuses.

## The publish guard

**Event:** before a shell command runs.

**Decides** whether the command publishes. Split the command line on shell
separators and test each part, and test it again with quotes removed.

- A package upload to any registry, for whichever package managers the
  project uses: always a publish.
- A `git push`, where `push` is the subcommand: resolve the remote to a URL
  and compare its host against `gated_hosts` in the config. A push to a local
  path or an ungated host publishes nothing and is not prompted. A bare push
  goes to the current branch's upstream, or `origin`.
- A write through a hosting provider's command line tool, such as creating a
  release or a pull request: a publish.
- `git stash push` is a local operation and is not a push.

**Says:** a confirmation prompt, by returning the pre-tool decision "ask".
The reason says what the command looks like and that publication needs the
maintainer's go-ahead with a short brief: what is going out, its risk and
reversibility, and what was verified.

**Fails closed.** This is the one hook whose failure direction is the
opposite of the others. A payload that cannot be parsed, a remote that cannot
be resolved, and git not answering all produce the prompt. An unknown state
at a publish gate must mean "ask", never "proceed".

**Local commits are never gated.** A commit is private and reversible.

**Check:** an upload prompts; a push to a gated host prompts; a push to a
local bare repository is silent; `git status` is silent; garbage on standard
input prompts.

## The security scan

**Event:** after a file is written through an editor tool. Share the router's
process.

**Does:** matches the edited file, line by line, against a table of patterns
for its file type, skipping comment lines and the bodies of docstrings.
Skips vendored, generated, and `.claude/` directories. The baseline for a
Python project covers unsafe deserialization, dynamic code execution, shell
invocation with a shell, disabled TLS verification, hardcoded secrets,
disabled template escaping, string-built SQL, debug mode, wildcard origins,
and archive extraction without a filter. For web files it covers raw HTML
sinks, script URLs, and a sandbox that grants both scripts and same origin.
Write the equivalent table for the project's own language.

**Says:** a blocking finding returns the post-tool decision "block" with the
line, the check id, and why it matters. A warning returns as added context.
In a test file, a hardcoded secret and a debug flag are warnings.

**Suppression is deliberate and greppable:** a trailing comment on the line,
`<slug>: allow <check-id> - <reason>`, silences that one check there.

**When the router also blocks the same edit,** add the scan's text to the
router's message on standard error. An exit of 2 is read from standard error,
and anything printed beside it is lost.

**A false negative is worse than noise.** On source it cannot parse, the scan
reads the text unmasked: noisy, never blind.

## The batch checks

**Event:** after a batch of tool calls resolves. **Measured:** this event
fires for a batch of one, so single edits are covered. The response for each
call arrives as text, so take edited paths from each call's input. A "block"
on this event ends the turn instead of handing the failure to the session,
so return every failure as added context.

Run each of these at most once per batch, never once per edited file.

**The test suite.** When an edit touched the source root, the test directory,
or the project's manifest, run the configured test command once in the
repository that owns the edited file. Find that repository by walking up from
the file to the configured root marker, so an edit in a git worktree runs
that worktree's suite and not the main tree's. Silent when green. On failure
return the tail of the output. A timeout is advice, not a failure: say it may
be a hang or a suite that outgrew its budget, in full once per session and in
one line after that.

**The dependency audit.** When a dependency manifest was edited, run the
ecosystem's own auditor once per ecosystem, so a manifest and its lockfile
edited together are audited once. A missing auditor is reported as
"unchecked", never as clean. A known vulnerability is context. A package on
the project's `banned` list is a block, checked in every manifest edited.

**The artifact check.** Only for a project that ships a package. When
packaging config was edited, build into a temporary directory and inspect the
real contents: nothing matching `forbidden` is inside, and everything in
`required_in_wheel` is. Reasoning about what a build tool includes is not
evidence; building is.

Run the suite and the build one after the other, since both execute the
tree. Run the audit beside them. Keep the worst case of the whole hook under
its own timeout, or one slow check loses every result.

## The turn-end reminder

**Event:** when the session's turn ends.

**Does two things, each once per session per rule:**

- Names any `required` rule the router fired this session whose consult is
  still not on the ledger.
- Compares the working tree against the last commit, matches the changed
  paths against the routing table, and names any `required` rule the router
  never saw. This covers a file changed by a shell command or a git
  operation, which the router is never told about.

**Measured:** text returned on this event is answered by the session as
feedback, so a reminder repeated at every turn end forces a continuation
every time. Say each thing once. Never return a block.

## The session rebrief

**Event:** when a session starts, for every kind of start: startup, resume,
clear, and compaction. A compaction is a session start in the middle of the
work, and what the engine had established is at the mercy of a summary.

**Says, only when there is something to say:** the consults the router
demanded this session that are still owed; the agents that edited the tree
since the last commit; how many claims are waiting for a verdict; and which
seats were consulted inside the freshness window, so a rebuilt session does
not pay for a round it already ran. Plain text on standard output.

On a plain startup it also says when the routing table or the agents
directory is missing, and keeps saying it every session until that is fixed.
A half-built setup is damage, not a user who has not started.

## The claim queue

**Event:** when a subagent finishes. Share the ledger's process.

**Does:** when the agent is a seat, meaning a file of that name exists in
`.claude/agents/`, reads its final message and appends every line carrying a
claim label (`[verified]`, `[measured]`, `[read]`, `[reasoned]`,
`[asserted]`) to `.claude/.pending-findings`: time, seat, label, and the
claim trimmed to about 240 characters. A report with no labels gets one row
saying so. Cap one report at 20 rows and record that the cap was hit.

Nothing prunes this queue. A claim leaves it when a person gives it a verdict
in `.claude/agent-findings.md` or deletes the row after reading it.

Silent, never blocks. **Measured:** output printed on this event goes to the
subagent, not the session, so print nothing.
