#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --unknown-flag (unknown flag) =="
uv run repl --unknown-flag
echo "exit code: $?"

echo "== repl --script (missing value) =="
uv run repl --script
echo "exit code: $?"

echo "== repl --help =="
uv run repl --help
echo "exit code: $?"
