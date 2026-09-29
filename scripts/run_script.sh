#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --script scripts/startup/basic.repl =="
uv run repl --script scripts/startup/basic.repl
echo "exit code: $?"
