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


class ScriptError(ShellError):
    """Raised when a startup script cannot be loaded or read.

    Covers a missing file, a directory given instead of a file, a
    permission error, and content that is not valid UTF-8.
    """


class VFSLoadError(ShellError):
    """Raised when a VFS image cannot be loaded.

    Covers a missing file, a directory given instead of a file, a
    permission error, malformed XML, and XML that does not follow the VFS
    schema (unknown elements/attributes, bad mode, duplicate names, ...).
    """


class VFSPathError(ShellError):
    """Raised by ``VFS.resolve`` when a path cannot be found inside a VFS."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")
