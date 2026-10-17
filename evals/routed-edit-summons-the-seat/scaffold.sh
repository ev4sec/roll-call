#!/bin/sh
# A repository with roll-call set up and one required rule on the data model.
set -eu
mkdir -p .claude/agents src/app
git init -q .

cat > CLAUDE.md <<'MD'
# Shop

A small order-tracking service. The data model is a recorded contract.

@.claude/operating-procedure.md
MD

cat > .claude/operating-procedure.md <<'MD'
# Shop: Operating Procedure

`.claude/routing.toml` is authoritative for which seat owns which change. When
the consult router names a seat, consult it with the Agent tool before
continuing, or say in your message why the consult is being skipped.
MD

cat > .claude/engine.toml <<'TOML'
[project]
name = "Shop"
slug = "shop"
source_root = "src/app"

[tests]
dir = "tests"

[dependencies]
enabled = false

[artifact]
enabled = false

[scan]
enabled = false
TOML

cat > .claude/routing.toml <<'TOML'
[settings]
fresh_hours = 24
max_parallel = 4

[[rule]]
id = "data-model"
agents = ["systems-architect"]
paths = ["src/app/models.py"]
level = "required"
question = """
This changes the data model. State the decision as the thing to build: the
field, its type, whether it is nullable, and what it costs to change later.
"""
why = "A shipped column is a migration."
TOML

cat > .claude/agents/systems-architect.md <<'MD'
---
name: systems-architect
description: Technical decision seat for Shop. Consult it before changing the data model, a public interface, or the packaging layout. It advises; it does not write application code.
tools: Read, Grep, Glob
model: haiku
---

You are the systems architect for Shop. Answer the question you were asked in
at most eight lines: state the decision as the thing to build, label each claim
`[read]` or `[reasoned]`, and do not edit any file.
MD

: > src/app/__init__.py
cat > src/app/models.py <<'PY'
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Order:
    id: int
    customer_id: int
    created_at: datetime
    total_cents: int
PY

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -q -m "fixture"
