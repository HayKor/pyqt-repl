#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs vfs/minimal.xml --script scripts/startup/vfs_info.repl =="
uv run repl --vfs vfs/minimal.xml --script scripts/startup/vfs_info.repl
echo "exit code: $?"
