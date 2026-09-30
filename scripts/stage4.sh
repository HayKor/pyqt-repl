#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage4.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage4.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_ls_missing_path.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_ls_missing_path.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_ls_bad_option.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_ls_bad_option.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_cd_into_file.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_cd_into_file.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_cd_missing_path.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_cd_missing_path.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_cat_directory.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_cat_directory.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_cat_missing_file.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_cat_missing_file.repl
echo "exit code: $?"

echo "== repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_tac_missing_operand.repl =="
uv run env HOME=/home/user repl --vfs vfs/deep.xml --script scripts/startup/stage4_err_tac_missing_operand.repl
echo "exit code: $?"
