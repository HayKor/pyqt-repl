#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --script scripts/startup/with_error.repl (command error aborts script) =="
uv run repl --script scripts/startup/with_error.repl
echo "exit code: $?"

echo "== repl --script scripts/startup/bad_args.repl (argument error aborts script) =="
uv run repl --script scripts/startup/bad_args.repl
echo "exit code: $?"

echo "== repl --script /no/such/script.repl (missing script file) =="
uv run repl --script /no/such/script.repl
echo "exit code: $?"
