"""Shell exceptions and process exit codes."""

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 127


class ShellError(Exception):
    """Base class for all shell errors."""

    pass


class ParseError(ShellError):
    """Unterminated quotes and such."""


class CommandNotFoundError(ShellError):
    """Unknown command name (exit code 127)."""

    def __init__(self, name: str) -> None:
        """Remember the name and build the bash-like message."""
        self.name = name
        super().__init__(f"repl: {name}: command not found")


class CommandArgsError(ShellError):
    """Bad command arguments (exit code 2); the message is shown as is."""

    pass


class ScriptError(ShellError):
    """Script file is missing, unreadable or not UTF-8."""


class VFSLoadError(ShellError):
    """The VFS XML can't be read or is broken."""


class VFSPathError(ShellError):
    """Path that cannot be resolved in the VFS."""

    def __init__(self, path: str, reason: str) -> None:
        """Keep the path as typed and the reason for the message."""
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")
