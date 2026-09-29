#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs pyproject.toml (existing path) =="
uv run repl --vfs pyproject.toml
echo "exit code: $?"

echo "== repl --vfs /no/such/vfs.xml (missing path) =="
uv run repl --vfs /no/such/vfs.xml
echo "exit code: $?"
