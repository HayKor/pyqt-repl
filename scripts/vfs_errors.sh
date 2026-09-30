#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

echo "== repl --vfs /no/such/vfs.xml (missing file) =="
uv run repl --vfs /no/such/vfs.xml
echo "exit code: $?"

echo "== repl --vfs vfs (a directory) =="
uv run repl --vfs vfs
echo "exit code: $?"

echo "== repl --vfs vfs/broken/not_xml.xml (invalid XML) =="
uv run repl --vfs vfs/broken/not_xml.xml
echo "exit code: $?"

echo "== repl --vfs vfs/broken/wrong_root.xml (wrong root element) =="
uv run repl --vfs vfs/broken/wrong_root.xml
echo "exit code: $?"

echo "== repl --vfs vfs/broken/bad_base64.xml (invalid base64) =="
uv run repl --vfs vfs/broken/bad_base64.xml
echo "exit code: $?"

echo "== repl --vfs vfs/broken/duplicate.xml (duplicate name) =="
uv run repl --vfs vfs/broken/duplicate.xml
echo "exit code: $?"

echo "== repl --vfs vfs/broken/bad_mode.xml (invalid mode) =="
uv run repl --vfs vfs/broken/bad_mode.xml
echo "exit code: $?"
