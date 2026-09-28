"""Exception hierarchy used by the shell core.

Every exception's ``str()`` is already the ready-to-print, bash-styled
error message.
"""

from __future__ import annotations


class ShellError(Exception):
    """Base class for all errors the shell core can raise."""


class ParseError(ShellError):
    """Raised by the tokenizer on malformed input (e.g. unterminated quote)."""


class CommandNotFoundError(ShellError):
    """Raised when the first word of a command line is not a known command."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"repl: {name}: command not found")


class CommandArgsError(ShellError):
    """Raised by a command implementation when arguments are invalid."""
