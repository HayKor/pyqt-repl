#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs pyproject.toml --script scripts/startup/exit.repl =="
uv run repl --vfs pyproject.toml --script scripts/startup/exit.repl
echo "exit code: $?"
