# Reproduction scripts

Kept because **a finding whose reproduction lives in a temp directory is a
finding the next session has to re-derive.**

## What belongs here rather than in the suite

Not every reproduction can be a test, and forcing one into the suite is how a
suite gets slow and flaky. A script belongs here when it is:

- **Probabilistic.** An arm that fails five times in twelve is a real finding
  and a terrible test. Keep the trial count and the observed rate in the header.
- **Slow, or dependent on wall-clock timing.** A growth curve, a stall
  measurement, a contention experiment.
- **A demonstration of something already fixed**, kept so the next person can
  see the failure rather than read about it.
- **An acceptance criterion for work not yet done.** The lines that currently
  report CLEAN are the definition of done.

## The rule that makes them trustworthy

**Every script carries its own positive control, and a run without the control
passing proves nothing.** A reproduction that reports "no failures" is
indistinguishable from a reproduction that did not actually apply, which has
happened: a mutation through a shell heredoc silently matched nothing, the
suite reported all green, and that read as *"the guard is weak"* when the truth
was the exact opposite.

State in each header:

- what it demonstrates, and whether that is open or fixed (name the commit);
- the **control**, and what the control must report;
- the numbers, if the finding is statistical;
- whether it touches the network. It should not.

## Scripts

<!-- One entry per script, in the shape above. Delete an entry when its finding
     is discharged AND the property it proved has a test; keep it while the
     property is only proven here. -->

- `{{repro_x.py}}`: {{what it demonstrates}}. **{{Open | Fixed in <commit>}}**.
  Control: {{what must report caught}}.

Run from the repository root with the project's environment.
