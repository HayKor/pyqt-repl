#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage5.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage5.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chmod_invalid_mode.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chmod_invalid_mode.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chmod_missing_operand.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chmod_missing_operand.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chmod_missing_file.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chmod_missing_file.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chown_invalid_user.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chown_invalid_user.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chown_invalid_group.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chown_invalid_group.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chmod_invalid_option.repl =="
uv run repl --vfs vfs/deep.xml --script scripts/startup/stage5_err_chmod_invalid_option.repl
echo "exit code: $?"
