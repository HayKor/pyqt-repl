"""The shell core: ties the parser and the command registry together.

Contains no Qt imports so it can be exercised by plain pytest and reused
by any future front-end (GUI now, a start-up script or a VFS later).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os

from .commands import REGISTRY, Command
from .errors import CommandArgsError, CommandNotFoundError, ParseError
from .parser import tokenize


@dataclass
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    should_exit: bool = False


class Shell:
    """Executes one command line at a time, keeping track of ``$?``."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        commands: Mapping[str, Command] = REGISTRY,
    ) -> None:
        self.env: dict[str, str] = dict(env) if env is not None else dict(os.environ)
        self.commands = commands
        self.last_exit_code = 0

    def _env_with_status(self) -> dict[str, str]:
        return {**self.env, "?": str(self.last_exit_code)}

    def execute(self, line: str) -> ExecResult:
        """Parse and run ``line``. Never raises ``ShellError``."""
        try:
            argv = tokenize(line, env=self._env_with_status())
        except ParseError as exc:
            self.last_exit_code = 2
            return ExecResult(stderr=str(exc), exit_code=2)

        if not argv:
            return ExecResult(exit_code=self.last_exit_code)

        command = self.commands.get(argv[0])
        if command is None:
            self.last_exit_code = 127
            return ExecResult(stderr=str(CommandNotFoundError(argv[0])), exit_code=127)

        try:
            result = command.run(argv[1:], self.last_exit_code)
        except CommandArgsError as exc:
            self.last_exit_code = 2
            return ExecResult(stderr=str(exc), exit_code=2)

        self.last_exit_code = result.exit_code
        return ExecResult(
            stdout=result.output,
            exit_code=result.exit_code,
            should_exit=result.should_exit,
        )
