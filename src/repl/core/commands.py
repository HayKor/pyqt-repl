import math
import re
import stat
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import ClassVar

from .errors import CommandArgsError, VFSPathError
from .modes import ModeError, looks_like_symbolic_mode, parse_mode
from .vfs import VDir, VFile, VFS, VNode

_LS_VALID_OPTIONS = frozenset("alh")
_CAT_VALID_OPTIONS = frozenset("n")
_DIR_SIZE = 4096
_SIZE_UNITS = ("", "K", "M", "G", "T", "P")
_OWNER_NAME_RE = re.compile(r"[a-z_][a-z0-9_-]*|[0-9]+")


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


def _walk(node: VNode) -> Iterator[VNode]:
    """Yield ``node`` itself, then (for a directory) every descendant.

    Shared by ``chmod -R``/``chown -R`` to apply their change to a whole
    subtree instead of just the named node.
    """
    yield node
    if isinstance(node, VDir):
        for child in node.children.values():
            yield from _walk(child)


def _resolve_targets(
    cmd: str, paths: list[str], ctx: CommandContext, *, recursive: bool
) -> tuple[list[VNode], list[str]]:
    """Resolve ``paths`` against ``ctx``, expanding each via ``_walk`` if
    ``recursive``. Returns ``(targets, error_messages)``; a path that
    fails to resolve contributes only to the error list, exactly like
    ``cat``/``tac``'s per-path error handling.
    """
    targets: list[VNode] = []
    errors: list[str] = []
    for p in paths:
        try:
            node = ctx.vfs.resolve(p, ctx.cwd)
        except VFSPathError as exc:
            errors.append(f"{cmd}: cannot access '{p}': {exc.reason}")
            continue
        targets.extend(_walk(node) if recursive else [node])
    return targets, errors


_CHMOD_MODE_LETTERS = frozenset("rwxXst")


class ChmodCommand(Command):
    name = "chmod"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        recursive = False
        mode_spec: str | None = None
        paths: list[str] = []

        for arg in args:
            is_dash_option = arg.startswith("-") and len(arg) > 1
            if arg == "-R":
                recursive = True
            elif mode_spec is None and is_dash_option and (
                arg[1] in _CHMOD_MODE_LETTERS or looks_like_symbolic_mode(arg)
            ):
                # Like GNU: "-x" or even a malformed "-wz" is the MODE operand,
                # so the latter is reported as an invalid mode, not an option.
                mode_spec = arg
            elif is_dash_option:
                raise CommandArgsError(f"chmod: invalid option -- '{arg[1]}'")
            elif mode_spec is None:
                mode_spec = arg
            else:
                paths.append(arg)

        if mode_spec is None:
            raise CommandArgsError("chmod: missing operand")
        if not paths:
            raise CommandArgsError(f"chmod: missing operand after '{mode_spec}'")

        try:
            parse_mode(mode_spec, 0)
        except ModeError:
            return CommandResult(error=f"chmod: invalid mode: '{mode_spec}'", exit_code=1)

        targets, errors = _resolve_targets("chmod", paths, ctx, recursive=recursive)
        for node in targets:
            node.mode = parse_mode(mode_spec, node.mode)

        return CommandResult(error="\n".join(errors), exit_code=1 if errors else 0)


class _InvalidOwnerSpec(Exception):
    """Raised by ``_parse_owner_spec`` for a malformed OWNER[:GROUP] spec."""


def _valid_owner_name(name: str) -> bool:
    return bool(_OWNER_NAME_RE.fullmatch(name))


def _parse_owner_spec(spec: str) -> tuple[str | None, str | None]:
    """Parse ``OWNER[:GROUP]`` into ``(new_owner, new_group)``.

    Either half is ``None`` when that part should be left unchanged:
    ``"user"``/``"user:"`` leave the group alone (a simplification of
    GNU's "user's login group" behaviour, documented in the plan/README),
    ``":group"`` leaves the owner alone. Raises ``_InvalidOwnerSpec`` for
    an empty spec, a bare ``":"``, or a name that is neither
    ``^[a-z_][a-z0-9_-]*$`` nor purely numeric (uid/gid stored as text).
    """
    if ":" not in spec:
        if not _valid_owner_name(spec):
            raise _InvalidOwnerSpec(f"invalid user: '{spec}'")
        return spec, None

    owner_part, group_part = spec.split(":", 1)
    if owner_part == "" and group_part == "":
        raise _InvalidOwnerSpec(f"invalid user: '{spec}'")

    new_owner = None
    new_group = None
    if owner_part != "":
        if not _valid_owner_name(owner_part):
            raise _InvalidOwnerSpec(f"invalid user: '{owner_part}'")
        new_owner = owner_part
    if group_part != "":
        if not _valid_owner_name(group_part):
            raise _InvalidOwnerSpec(f"invalid group: '{group_part}'")
        new_group = group_part
    return new_owner, new_group


class ChownCommand(Command):
    name = "chown"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        recursive = False
        owner_spec: str | None = None
        paths: list[str] = []

        for arg in args:
            if arg == "-R":
                recursive = True
            elif arg.startswith("-") and len(arg) > 1:
                raise CommandArgsError(f"chown: invalid option -- '{arg[1]}'")
            elif owner_spec is None:
                owner_spec = arg
            else:
                paths.append(arg)

        if owner_spec is None:
            raise CommandArgsError("chown: missing operand")
        if not paths:
            raise CommandArgsError(f"chown: missing operand after '{owner_spec}'")

        try:
            new_owner, new_group = _parse_owner_spec(owner_spec)
        except _InvalidOwnerSpec as exc:
            return CommandResult(error=f"chown: {exc}", exit_code=1)

        targets, errors = _resolve_targets("chown", paths, ctx, recursive=recursive)
        for node in targets:
            if new_owner is not None:
                node.owner = new_owner
            if new_group is not None:
                node.group = new_group

        return CommandResult(error="\n".join(errors), exit_code=1 if errors else 0)


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
    "chmod": ChmodCommand(),
    "chown": ChownCommand(),
    "vfs-info": VfsInfoCommand(),
}
