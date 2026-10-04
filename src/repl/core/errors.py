class ShellError(Exception):
    pass


class ParseError(ShellError):
    """unterminated quotes and such"""


class CommandNotFoundError(ShellError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"repl: {name}: command not found")


class CommandArgsError(ShellError):
    pass


class ScriptError(ShellError):
    """script file missing / unreadable / not utf-8"""


class VFSLoadError(ShellError):
    """can't read the vfs xml or it's broken"""


class VFSPathError(ShellError):
    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")
