#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl (no arguments) =="
uv run repl
echo "exit code: $?"
