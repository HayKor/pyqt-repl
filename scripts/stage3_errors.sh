#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage3_err_unknown.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage3_err_unknown.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage3_err_ls.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage3_err_ls.repl
echo "exit code: $?"

echo "== repl --script scripts/startup/vfs_info.repl (no --vfs) =="
uv run repl --script scripts/startup/vfs_info.repl
echo "exit code: $?"
