"""Stub command implementations and the command registry.

Stage 1 only has to prove that commands are dispatched, print their name
and parsed arguments, and can validate arguments. Real filesystem
behaviour for ``ls``/``cd`` is out of scope until the VFS stage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from .errors import CommandArgsError

_LS_VALID_OPTIONS = frozenset("alh")


@dataclass
class CommandResult:
    output: str = ""
    exit_code: int = 0
    should_exit: bool = False


class Command(ABC):
    """Base class for all shell commands."""

    name: ClassVar[str]

    @abstractmethod
    def run(self, args: list[str], last_exit_code: int = 0) -> CommandResult:
        """Execute the command.

        ``last_exit_code`` is the previous command's exit status; only
        ``exit`` (mirroring bash) makes use of it. Raises
        ``CommandArgsError`` for invalid arguments.
        """


class LsCommand(Command):
    name = "ls"

    def run(self, args: list[str], last_exit_code: int = 0) -> CommandResult:
        for arg in args:
            if arg.startswith("-") and len(arg) > 1:
                for opt in arg[1:]:
                    if opt not in _LS_VALID_OPTIONS:
                        raise CommandArgsError(f"ls: invalid option -- '{opt}'")
        return CommandResult(output=f"ls: args={args!r}")


class CdCommand(Command):
    name = "cd"

    def run(self, args: list[str], last_exit_code: int = 0) -> CommandResult:
        if len(args) > 1:
            raise CommandArgsError("cd: too many arguments")
        return CommandResult(output=f"cd: args={args!r}")


class ExitCommand(Command):
    name = "exit"

    def run(self, args: list[str], last_exit_code: int = 0) -> CommandResult:
        if len(args) > 1:
            raise CommandArgsError("exit: too many arguments")
        if not args:
            return CommandResult(exit_code=last_exit_code, should_exit=True)
        try:
            code = int(args[0])
        except ValueError:
            raise CommandArgsError(
                f"exit: {args[0]}: numeric argument required"
            ) from None
        return CommandResult(exit_code=code, should_exit=True)


REGISTRY: dict[str, Command] = {
    "ls": LsCommand(),
    "cd": CdCommand(),
    "exit": ExitCommand(),
}
