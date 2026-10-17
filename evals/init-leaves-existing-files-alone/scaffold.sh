#!/bin/sh
# A Python repository that already has its own CLAUDE.md.
set -eu
mkdir -p src/widget tests
git init -q .

cat > CLAUDE.md <<'MD'
# Mine

House rules written before any plugin arrived. Keep this line: SENTINEL-7731.
MD

cat > pyproject.toml <<'TOML'
[project]
name = "widget"
version = "0.1.0"
TOML

: > src/widget/__init__.py
cat > tests/test_truth.py <<'PY'
def test_truth():
    assert True
PY

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -q -m "fixture"
