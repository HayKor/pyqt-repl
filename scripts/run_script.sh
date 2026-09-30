#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs vfs/deep.xml --script scripts/startup/basic.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/basic.repl
echo "exit code: $?"
