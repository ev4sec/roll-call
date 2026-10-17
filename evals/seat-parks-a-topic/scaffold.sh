#!/bin/sh
# A roster of three seats and an empty parked-roles register.
set -eu
mkdir -p .claude/agents
git init -q .

cat > CLAUDE.md <<'MD'
# Ledgerly

A bookkeeping service. The roster is capped; a seat earns its place only with
a distinct standard of evidence.
MD

cat > .claude/operating-procedure.md <<'MD'
# Ledgerly: Operating Procedure

An agent earns a seat only if it brings a **distinct standard of evidence**.
Not a distinct topic, but a distinct way of being right.
MD

cat > .claude/routing.toml <<'TOML'
[settings]
fresh_hours = 24

[[rule]]
id = "data-model"
agents = ["systems-architect"]
paths = ["src/ledgerly/models.py", "src/ledgerly/store/**"]
level = "required"
question = "State the field, its type, nullability, and what a migration costs."
why = "A shipped column is a migration."

[[rule]]
id = "untrusted-input"
agents = ["security-engineer"]
paths = ["src/ledgerly/net/**"]
level = "required"
question = "Name the trust boundary and what hostile input reaches."
why = "A single chokepoint is a structural property."

[[rule]]
id = "scope-moves"
agents = ["scope-validator"]
paths = [".claude/slice.md"]
level = "advised"
question = "Should this be built at all, now?"
why = "Scope creep arrives as an extra line in the slice file."
TOML

cat > .claude/agents/systems-architect.md <<'MD'
---
name: systems-architect
description: Staff-level technical decision seat for Ledgerly. Owns storage and data-model design, query shape, concurrency, interface shape, and any "which approach and why" tradeoff. Its standard of evidence is measurement. Distinct from security-engineer, which demonstrates what an adversary reaches rather than which design is right.
tools: Read, Grep, Glob, Bash
model: haiku
---

You measure. You run the thing and report what it did.
MD

cat > .claude/agents/security-engineer.md <<'MD'
---
name: security-engineer
description: Application-security seat for Ledgerly. Threat-models before code exists and reviews diffs for defects. Its standard of evidence is exploitation. Distinct from systems-architect, which decides which design is right rather than what an adversary reaches.
tools: Read, Grep, Glob, Bash
model: haiku
---

You exploit. A finding without an exploit path is a hypothesis.
MD

cat > .claude/agents/scope-validator.md <<'MD'
---
name: scope-validator
description: Product and scope conscience for Ledgerly. Refuses by citing the record. Distinct from systems-architect, which answers how, not whether.
tools: Read, Grep, Glob
model: haiku
---

You refuse by pointing at a line in a file in this repository.
MD

cat > .claude/parked-roles.md <<'MD'
# Parked roles

Roles considered for the roster and not adopted, each with the trigger that
would make it right. A rejected idea with no record gets re-proposed from
scratch every few months.

| Role proposed | Why it did not earn a seat | What would change the answer |
|---|---|---|
MD

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -q -m "fixture"
