"""Command implementations and the command registry.

``ls`` and ``cd`` are real now: they resolve paths against ``ctx.vfs``
(``VFS.resolve``/``normalize``) instead of just echoing their arguments.
``cat``/``tac`` are new commands that read file content out of the VFS.
``vfs-info`` is unchanged from the previous stage.

None of this module imports Qt; everything here is plain Python over the
in-memory VFS model from ``core/vfs.py``.
"""

from __future__ import annotations

import math
import stat
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from .errors import CommandArgsError, VFSPathError
from .vfs import VDir, VFile, VFS, VNode

_LS_VALID_OPTIONS = frozenset("alh")
_CAT_VALID_OPTIONS = frozenset("n")
_DIR_SIZE = 4096
_SIZE_UNITS = ("", "K", "M", "G", "T", "P")


@dataclass
class CommandContext:
    """Everything a command needs beyond its own argument list."""

    vfs: VFS
    cwd: str
    last_exit_code: int
    env: Mapping[str, str]
    oldpwd: str | None = None


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


def _mode_string(node: VNode) -> str:
    kind = stat.S_IFDIR if isinstance(node, VDir) else stat.S_IFREG
    return stat.filemode(kind | node.mode)


def _display_size(node: VNode) -> int:
    return _DIR_SIZE if isinstance(node, VDir) else node.size  # type: ignore[union-attr]


def _human_size(n: int) -> str:
    """Format ``n`` bytes the way GNU ``ls -h`` roughly does.

    One digit after the decimal point while the scaled value is below 10,
    rounded up; a bare integer above that. Plain bytes (< 1024) are printed
    without a unit suffix.
    """
    size = float(n)
    unit = 0
    while size >= 1024 and unit < len(_SIZE_UNITS) - 1:
        size /= 1024
        unit += 1
    if unit == 0:
        return str(n)
    if size < 10:
        value = math.ceil(size * 10) / 10
        return f"{value:.1f}{_SIZE_UNITS[unit]}"
    return f"{math.ceil(size)}{_SIZE_UNITS[unit]}"


def _format_listing(
    entries: list[tuple[str, VNode]],
    *,
    long_format: bool,
    human: bool,
    show_total: bool,
) -> str:
    """Render ``entries`` (name, node) pairs as one ``ls`` block.

    ``show_total`` requests the ``total N`` header line that precedes a
    directory's contents in ``-l`` mode (ignored outside ``-l``); ``N`` is
    simply the number of entries shown, not a real disk-block count.
    """
    lines: list[str] = []
    if show_total and long_format:
        lines.append(f"total {len(entries)}")
    if not entries:
        return "\n".join(lines)

    if not long_format:
        lines.append("  ".join(name for name, _ in entries))
        return "\n".join(lines)

    modes = [_mode_string(node) for _, node in entries]
    owners = [node.owner for _, node in entries]
    groups = [node.group for _, node in entries]
    size_values = [_display_size(node) for _, node in entries]
    size_strs = [_human_size(s) if human else str(s) for s in size_values]

    owner_w = max(len(o) for o in owners)
    group_w = max(len(g) for g in groups)
    size_w = max(len(s) for s in size_strs)

    for (name, _node), mode, owner, group, size_str in zip(
        entries, modes, owners, groups, size_strs, strict=True
    ):
        lines.append(f"{mode} {owner:<{owner_w}} {group:<{group_w}}  {size_str:>{size_w}} {name}")
    return "\n".join(lines)


def _dir_entries(vfs: VFS, path: str, cwd: str, node: VDir, show_all: bool) -> list[tuple[str, VNode]]:
    """List ``node``'s children as (name, node) pairs, sorted by name.

    With ``show_all``, ``.`` and ``..`` are prepended (``..`` is resolved
    via ``vfs.resolve(path + "/..", cwd)`` rather than a parent pointer,
    since the VFS tree does not keep one).
    """
    entries: list[tuple[str, VNode]] = []
    if show_all:
        entries.append((".", node))
        parent = vfs.resolve(f"{path}/..", cwd)
        entries.append(("..", parent))
    for name in sorted(node.children):
        if not show_all and name.startswith("."):
            continue
        entries.append((name, node.children[name]))
    return entries


class LsCommand(Command):
    name = "ls"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        show_all = False
        long_format = False
        human = False
        paths: list[str] = []

        for arg in args:
            if arg.startswith("-") and len(arg) > 1:
                for opt in arg[1:]:
                    if opt not in _LS_VALID_OPTIONS:
                        raise CommandArgsError(f"ls: invalid option -- '{opt}'")
                    if opt == "a":
                        show_all = True
                    elif opt == "l":
                        long_format = True
                    elif opt == "h":
                        human = True
            else:
                paths.append(arg)

        if not paths:
            paths = [ctx.cwd]
        show_headers = len(paths) > 1

        files: list[tuple[str, VNode]] = []
        dirs: list[tuple[str, VDir]] = []
        errors: list[str] = []
        for p in paths:
            try:
                node = ctx.vfs.resolve(p, ctx.cwd)
            except VFSPathError as exc:
                errors.append(f"ls: cannot access '{p}': {exc.reason}")
                continue
            if isinstance(node, VDir):
                dirs.append((p, node))
            else:
                files.append((p, node))

        files.sort(key=lambda item: item[0])

        blocks: list[str] = []
        if files:
            blocks.append(
                _format_listing(files, long_format=long_format, human=human, show_total=False)
            )
        for p, d in dirs:
            entries = _dir_entries(ctx.vfs, p, ctx.cwd, d, show_all)
            listing = _format_listing(entries, long_format=long_format, human=human, show_total=True)
            if not show_headers:
                blocks.append(listing)
            else:
                blocks.append(f"{p}:\n{listing}" if listing else f"{p}:")

        output = "\n\n".join(blocks)
        exit_code = 2 if errors else 0
        return CommandResult(output=output, error="\n".join(errors), exit_code=exit_code)


class CdCommand(Command):
    name = "cd"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        if len(args) > 1:
            raise CommandArgsError("cd: too many arguments")

        echo_new_path = False
        if args and args[0] == "-":
            if ctx.oldpwd is None:
                return CommandResult(error="cd: OLDPWD not set", exit_code=1)
            target = ctx.oldpwd
            echo_new_path = True
        else:
            target = args[0] if args else "/"

        try:
            node = ctx.vfs.resolve(target, ctx.cwd)
        except VFSPathError as exc:
            return CommandResult(error=f"cd: {exc}", exit_code=1)
        if not isinstance(node, VDir):
            return CommandResult(error=f"cd: {target}: Not a directory", exit_code=1)

        new_cwd = ctx.vfs.normalize(target, ctx.cwd)
        ctx.oldpwd = ctx.cwd
        ctx.cwd = new_cwd
        return CommandResult(output=new_cwd if echo_new_path else "")


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


class CatCommand(Command):
    name = "cat"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        numbered = False
        files: list[str] = []
        for arg in args:
            if arg.startswith("-") and len(arg) > 1:
                for opt in arg[1:]:
                    if opt not in _CAT_VALID_OPTIONS:
                        raise CommandArgsError(f"cat: invalid option -- '{opt}'")
                    numbered = True
            else:
                files.append(arg)

        if not files:
            raise CommandArgsError("cat: missing file operand")

        contents: list[str] = []
        errors: list[str] = []
        for p in files:
            try:
                node = ctx.vfs.resolve(p, ctx.cwd)
            except VFSPathError as exc:
                errors.append(f"cat: {exc}")
                continue
            if isinstance(node, VDir):
                errors.append(f"cat: {p}: Is a directory")
                continue
            contents.append(node.data.decode("utf-8", errors="replace"))

        text = "".join(contents)
        body = text[:-1] if text.endswith("\n") else text
        if numbered:
            lines = body.split("\n") if body else []
            output = "\n".join(f"{i:>6}\t{line}" for i, line in enumerate(lines, start=1))
        else:
            output = body

        exit_code = 1 if errors else 0
        return CommandResult(output=output, error="\n".join(errors), exit_code=exit_code)


def _tac_records(text: str) -> list[str]:
    """Split ``text`` into GNU-``tac``-style records (separator ``"\\n"``).

    Every record but a possible final, separator-less one keeps its
    trailing ``"\\n"`` glued on, exactly like ``tac`` reattaches it after
    reversing: ``tac_records("a\\nb")`` is ``["a\\n", "b"]``.
    """
    if text == "":
        return []
    parts = text.split("\n")
    if parts[-1] == "":
        return [p + "\n" for p in parts[:-1]]
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


def _tac(text: str) -> str:
    return "".join(reversed(_tac_records(text)))


class TacCommand(Command):
    name = "tac"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        files: list[str] = []
        for arg in args:
            if arg.startswith("-") and len(arg) > 1:
                raise CommandArgsError(f"tac: invalid option -- '{arg[1]}'")
            files.append(arg)

        if not files:
            raise CommandArgsError("tac: missing file operand")

        parts: list[str] = []
        errors: list[str] = []
        for p in files:
            try:
                node = ctx.vfs.resolve(p, ctx.cwd)
            except VFSPathError as exc:
                errors.append(f"tac: {exc}")
                continue
            if isinstance(node, VDir):
                errors.append(f"tac: {p}: Is a directory")
                continue
            text = node.data.decode("utf-8", errors="replace")
            parts.append(_tac(text))

        output = "".join(parts)
        if output.endswith("\n"):
            output = output[:-1]

        exit_code = 1 if errors else 0
        return CommandResult(output=output, error="\n".join(errors), exit_code=exit_code)


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
    "cat": CatCommand(),
    "tac": TacCommand(),
    "vfs-info": VfsInfoCommand(),
}
