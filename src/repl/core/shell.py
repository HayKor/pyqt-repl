"""Shell: ties the parser, commands and VFS together."""

from collections.abc import Mapping
from dataclasses import dataclass
import os

from .commands import REGISTRY, Command, CommandContext
from .errors import (
    EXIT_NOT_FOUND,
    EXIT_USAGE,
    CommandArgsError,
    CommandNotFoundError,
    ParseError,
)
from .parser import tokenize
from .vfs import VFS


@dataclass
class ExecResult:
    """What one executed line produced."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    should_exit: bool = False


class Shell:
    """Command interpreter state: env, VFS, cwd, OLDPWD and ``$?``."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        commands: Mapping[str, Command] = REGISTRY,
        vfs: VFS | None = None,
    ) -> None:
        """Create a shell; env defaults to os.environ, VFS to an empty one."""
        self.env: dict[str, str] = (
            dict(env) if env is not None else dict(os.environ)
        )
        self.commands = commands
        self.vfs = vfs if vfs is not None else VFS.empty()
        self.cwd = "/"
        self.oldpwd: str | None = None
        self.last_exit_code = 0

    def _env_with_status(self) -> dict[str, str]:
        return {**self.env, "?": str(self.last_exit_code)}

    def _fail(self, exit_code: int, message: str) -> ExecResult:
        """Record a failed line in ``$?`` and report it on stderr."""
        self.last_exit_code = exit_code
        return ExecResult(stderr=message, exit_code=exit_code)

    def execute(self, line: str) -> ExecResult:
        """Run one command line; never raises, errors go to stderr."""
        try:
            argv = tokenize(line, env=self._env_with_status())
        except ParseError as exc:
            return self._fail(EXIT_USAGE, str(exc))

        if not argv:
            return ExecResult(exit_code=self.last_exit_code)

        command = self.commands.get(argv[0])
        if command is None:
            return self._fail(
                EXIT_NOT_FOUND, str(CommandNotFoundError(argv[0]))
            )

        ctx = CommandContext(
            vfs=self.vfs,
            cwd=self.cwd,
            last_exit_code=self.last_exit_code,
            env=self.env,
            oldpwd=self.oldpwd,
        )
        try:
            result = command.run(argv[1:], ctx)
        except CommandArgsError as exc:
            return self._fail(EXIT_USAGE, str(exc))
        self.cwd = ctx.cwd
        self.oldpwd = ctx.oldpwd

        self.last_exit_code = result.exit_code
        return ExecResult(
            stdout=result.output,
            stderr=result.error,
            exit_code=result.exit_code,
            should_exit=result.should_exit,
        )
