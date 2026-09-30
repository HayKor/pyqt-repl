"""Command implementations and the command registry.

``ls``/``cd`` are still stubs here: they prove that commands are
dispatched, print their name and parsed arguments, and can validate
arguments, but real VFS-backed behaviour is out of scope until the
commands stage. ``vfs-info`` is the one fully real command this stage
adds, since it only needs to report on the already-loaded ``VFS``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from .errors import CommandArgsError
from .vfs import VFS

_LS_VALID_OPTIONS = frozenset("alh")


@dataclass
class CommandContext:
    """Everything a command needs beyond its own argument list."""

    vfs: VFS
    cwd: str
    last_exit_code: int
    env: Mapping[str, str]


@dataclass
class CommandResult:
    output: str = ""
    error: str = ""
    exit_code: int = 0
    should_exit: bool = False


class Command(ABC):
    """Base class for all shell commands."""

    name: ClassVar[str]

    @abstractmethod
    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Execute the command against ``args`` and the current ``ctx``.

        Raises ``CommandArgsError`` for invalid arguments.
        """


class LsCommand(Command):
    name = "ls"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        for arg in args:
            if arg.startswith("-") and len(arg) > 1:
                for opt in arg[1:]:
                    if opt not in _LS_VALID_OPTIONS:
                        raise CommandArgsError(f"ls: invalid option -- '{opt}'")
        return CommandResult(output=f"ls: args={args!r}")


class CdCommand(Command):
    name = "cd"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        if len(args) > 1:
            raise CommandArgsError("cd: too many arguments")
        return CommandResult(output=f"cd: args={args!r}")


class ExitCommand(Command):
    name = "exit"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        if len(args) > 1:
            raise CommandArgsError("exit: too many arguments")
        if not args:
            return CommandResult(exit_code=ctx.last_exit_code, should_exit=True)
        try:
            code = int(args[0])
        except ValueError:
            raise CommandArgsError(
                f"exit: {args[0]}: numeric argument required"
            ) from None
        return CommandResult(exit_code=code, should_exit=True)


class VfsInfoCommand(Command):
    name = "vfs-info"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        if args:
            raise CommandArgsError("vfs-info: too many arguments")
        if not ctx.vfs.loaded:
            return CommandResult(error="vfs-info: no VFS loaded", exit_code=1)
        output = f"name: {ctx.vfs.name}\nsha256: {ctx.vfs.sha256}"
        return CommandResult(output=output)


REGISTRY: dict[str, Command] = {
    "ls": LsCommand(),
    "cd": CdCommand(),
    "exit": ExitCommand(),
    "vfs-info": VfsInfoCommand(),
}
