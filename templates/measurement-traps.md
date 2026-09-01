# Known measurement traps

Read this before carrying a `[measured]` or `[verified]` claim about
performance, concurrency, builds, packaging, tooling, tests and their
oracles, or what an environment actually has installed. Each entry produced a
confidently wrong conclusion on a real project.

<!-- INSTANTIATION: this list starts with the entries that generalize and
     fills as the project is burned. It lives in its own file, rather than in
     agent-brief.md where it used to, because the brief is read by every seat
     on every consult while these entries matter only to the consults that
     measure. Growth is welcome here; it costs tokens only where it pays. -->

- **Counting loop iterations does not measure contention.** The sampling window
  closes before the worker enters the blocking call, so the count looks normal
  and you conclude the lock was free. Measure the **maximum gap between
  consecutive `perf_counter()` samples** instead. This produced a false negative
  for two different reviewers on the same question, in the same session.
- **A single timing proves nothing about a pattern; growth is the signal.**
  `(a+)+$` is imperceptible at n=20 and twenty-one seconds at n=28. Report a
  curve.
- **"It is optimized away on this version" needs a timing, not a
  recollection.** That exact claim has been made and was false.
- **Reasoning about a build backend is not evidence about this repository.**
  `.git/info/exclude` hides paths from git but not from the packager. Build the
  artifact and read it.
- **A rule that holds for one member of a family can fail for another.** Before
  generalizing across a family of transformations, check the member with the
  least convenient algebra.
- **Your environment is not the project's floor.** Say which version and
  platform you measured on.
- **Declared is not installed, and a green suite proves neither.** Two test
  plugins were listed in the dev extras and absent from the environment the
  suite ran in. The second was worse: a config option was set, the runner
  printed `Unknown config option` on every run, and **no async test was
  collected at all**, so the only async code in the tree had never executed.
  **Two absent things can hold each other up.** When you claim a check runs,
  verify the checker is installed, not that the manifest mentions it.
- **A green type-check on your own OS is not evidence about any other.** Type
  checkers evaluate platform comparisons *for the platform they run on*, so a
  platform dispatch written as an if/elif chain narrows differently per OS. A
  file passed on Windows and failed CI on Linux with `Statement is unreachable`.
  Prefer a dict keyed by platform over branches, and run the checker for each
  target platform.
- **A mutation test that does not apply looks exactly like a passing one.**
  Mutating a file through a shell heredoc, a `str.replace()` whose target
  contained `\x00` silently matched nothing: the backslash was consumed before
  Python saw it. The suite then reported all green, which reads as *"this guard
  is weak, the mutation survived"* and is the exact opposite of the truth.
  **Assert the mutation landed before believing the result:** diff the file, or
  mutate with an editor rather than a shell heredoc.
- **A carve-out in a guard needs more tests on its boundary than in its
  middle.** If you propose narrowing a guard, propose the boundary cases in the
  same breath.
