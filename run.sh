#!/usr/bin/env bash
# Launch the REPL emulator; all arguments are passed through (--vfs, --script).
set -euo pipefail
cd "$(dirname "$0")"
exec uv run repl "$@"
