#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage3.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage3.repl
echo "exit code: $?"
