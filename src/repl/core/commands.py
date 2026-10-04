"""Built-in commands and their registry."""

import math
import re
import stat
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import ClassVar

from .errors import (
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_USAGE,
    CommandArgsError,
    VFSPathError,
)
from .modes import ModeError, looks_like_symbolic_mode, parse_mode
from .vfs import VDir, VFile, VFS, VNode

_LS_OPTION_FIELDS = {"a": "show_all", "l": "long_format", "h": "human"}
_CAT_VALID_OPTIONS = frozenset("n")
_DIR_SIZE = 4096
_SIZE_UNITS = ("", "K", "M", "G", "T", "P")
_SIZE_STEP = 1024
_ONE_DECIMAL_BELOW = 10
_OWNER_NAME_RE = re.compile(r"[a-z_][a-z0-9_-]*|[0-9]+")


@dataclass
class CommandContext:
    """State a command can read and change (cwd, OLDPWD)."""

    vfs: VFS
    cwd: str
    last_exit_code: int
    env: Mapping[str, str]
    oldpwd: str | None = None


@dataclass
class CommandResult:
    """Output, error text and exit code of a command."""

    output: str = ""
    error: str = ""
    exit_code: int = 0
    should_exit: bool = False


class Command(ABC):
    """Base class of built-in commands."""

    name: ClassVar[str]

    @abstractmethod
    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Run the command; raise CommandArgsError on bad arguments."""


def _mode_string(node: VNode) -> str:
    kind = stat.S_IFDIR if isinstance(node, VDir) else stat.S_IFREG
    return stat.filemode(kind | node.mode)


def _display_size(node: VNode) -> int:
    """Size for ``ls -l``: content length for files, 4096 for directories."""
    if isinstance(node, VFile):
        return node.size
    return _DIR_SIZE


def _human_size(n: int) -> str:
    """Format a size roughly like GNU ``ls -h``: 4.0K, 1.5M, 12M (rounds up)."""
    size = float(n)
    unit = 0
    while size >= _SIZE_STEP and unit < len(_SIZE_UNITS) - 1:
        size /= _SIZE_STEP
        unit += 1
    if unit == 0:
        return str(n)
    if size < _ONE_DECIMAL_BELOW:
        value = math.ceil(size * 10) / 10
        return f"{value:.1f}{_SIZE_UNITS[unit]}"
    return f"{math.ceil(size)}{_SIZE_UNITS[unit]}"


def _long_lines(entries: list[tuple[str, VNode]], human: bool) -> list[str]:
    """Render ``ls -l`` lines with owner/group/size aligned in columns."""
    sizes = [_display_size(node) for _, node in entries]
    size_strs = [_human_size(n) if human else str(n) for n in sizes]
    owner_w = max(len(node.owner) for _, node in entries)
    group_w = max(len(node.group) for _, node in entries)
    size_w = max(len(s) for s in size_strs)
    return [
        f"{_mode_string(node)} {node.owner:<{owner_w}} "
        f"{node.group:<{group_w}}  {size_str:>{size_w}} {name}"
        for (name, node), size_str in zip(entries, size_strs, strict=True)
    ]


def _format_listing(
    entries: list[tuple[str, VNode]],
    *,
    long_format: bool,
    human: bool,
    show_total: bool,
) -> str:
    """Render entries in short or ``-l`` format.

    "total N" is just the entry count, there are no real blocks here.
    """
    lines: list[str] = []
    if show_total and long_format:
        lines.append(f"total {len(entries)}")
    if entries and long_format:
        lines.extend(_long_lines(entries, human))
    elif entries:
        lines.append("  ".join(name for name, _ in entries))
    return "\n".join(lines)


def _dir_entries(
    vfs: VFS, path: str, cwd: str, node: VDir, show_all: bool
) -> list[tuple[str, VNode]]:
    entries: list[tuple[str, VNode]] = []
    if show_all:
        entries.append((".", node))
        # no parent pointers in the tree, so go through resolve
        parent = vfs.resolve(f"{path}/..", cwd)
        entries.append(("..", parent))
    for name in sorted(node.children):
        if not show_all and name.startswith("."):
            continue
        entries.append((name, node.children[name]))
    return entries


@dataclass
class _LsOptions:
    show_all: bool = False
    long_format: bool = False
    human: bool = False


def _parse_ls_args(args: list[str]) -> tuple[_LsOptions, list[str]]:
    """Split ``ls`` arguments into options and paths."""
    opts = _LsOptions()
    paths: list[str] = []
    for arg in args:
        if not (arg.startswith("-") and len(arg) > 1):
            paths.append(arg)
            continue
        for opt in arg[1:]:
            if opt not in _LS_OPTION_FIELDS:
                raise CommandArgsError(f"ls: invalid option -- '{opt}'")
            setattr(opts, _LS_OPTION_FIELDS[opt], True)
    return opts, paths


def _split_ls_paths(
    paths: list[str], ctx: CommandContext
) -> tuple[list[tuple[str, VNode]], list[tuple[str, VDir]], list[str]]:
    """Resolve paths -> (files sorted by name, dirs in order, error lines)."""
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
    return files, dirs, errors


class LsCommand(Command):
    """``ls [-a] [-l] [-h] [PATH...]`` over the VFS."""

    name = "ls"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """List files first, then each directory (with headers if several)."""
        opts, paths = _parse_ls_args(args)
        show_headers = len(paths) > 1
        files, dirs, errors = _split_ls_paths(paths or [ctx.cwd], ctx)

        blocks: list[str] = []
        if files:
            blocks.append(
                _format_listing(
                    files,
                    long_format=opts.long_format,
                    human=opts.human,
                    show_total=False,
                )
            )
        for p, d in dirs:
            entries = _dir_entries(ctx.vfs, p, ctx.cwd, d, opts.show_all)
            listing = _format_listing(
                entries,
                long_format=opts.long_format,
                human=opts.human,
                show_total=True,
            )
            if not show_headers:
                blocks.append(listing)
            else:
                blocks.append(f"{p}:\n{listing}" if listing else f"{p}:")

        return CommandResult(
            output="\n\n".join(blocks),
            error="\n".join(errors),
            exit_code=EXIT_USAGE if errors else EXIT_OK,
        )


class CdCommand(Command):
    """``cd [DIR]``, ``cd -`` goes back to OLDPWD."""

    name = "cd"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Change ``ctx.cwd``; ``cd -`` also prints the new path."""
        if len(args) > 1:
            raise CommandArgsError("cd: too many arguments")

        echo_new_path = False
        if args and args[0] == "-":
            if ctx.oldpwd is None:
                return CommandResult(
                    error="cd: OLDPWD not set", exit_code=EXIT_FAILURE
                )
            target = ctx.oldpwd
            echo_new_path = True
        else:
            target = args[0] if args else "/"

        try:
            node = ctx.vfs.resolve(target, ctx.cwd)
        except VFSPathError as exc:
            return CommandResult(error=f"cd: {exc}", exit_code=EXIT_FAILURE)
        if not isinstance(node, VDir):
            return CommandResult(
                error=f"cd: {target}: Not a directory", exit_code=EXIT_FAILURE
            )

        new_cwd = ctx.vfs.normalize(target, ctx.cwd)
        ctx.oldpwd = ctx.cwd
        ctx.cwd = new_cwd
        return CommandResult(output=new_cwd if echo_new_path else "")


class ExitCommand(Command):
    """``exit [N]``, closes the emulator."""

    name = "exit"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Ask the shell to exit with N or the last exit code."""
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


def _read_files(
    cmd: str, files: list[str], ctx: CommandContext
) -> tuple[list[str], list[str]]:
    """Decode each file as UTF-8 -> (texts, error lines) for cat/tac."""
    texts: list[str] = []
    errors: list[str] = []
    for p in files:
        try:
            node = ctx.vfs.resolve(p, ctx.cwd)
        except VFSPathError as exc:
            errors.append(f"{cmd}: {exc}")
            continue
        if isinstance(node, VDir):
            errors.append(f"{cmd}: {p}: Is a directory")
            continue
        texts.append(node.data.decode("utf-8", errors="replace"))
    return texts, errors


def _parse_cat_args(args: list[str]) -> tuple[bool, list[str]]:
    """Split ``cat`` arguments -> (numbered, files)."""
    numbered = False
    files: list[str] = []
    for arg in args:
        if not (arg.startswith("-") and len(arg) > 1):
            files.append(arg)
            continue
        for opt in arg[1:]:
            if opt not in _CAT_VALID_OPTIONS:
                raise CommandArgsError(f"cat: invalid option -- '{opt}'")
            numbered = True
    if not files:
        raise CommandArgsError("cat: missing file operand")
    return numbered, files


def _number_lines(body: str) -> str:
    """Prefix each line with its number, like GNU ``cat -n``."""
    lines = body.split("\n") if body else []
    return "\n".join(f"{i:>6}\t{line}" for i, line in enumerate(lines, start=1))


class CatCommand(Command):
    """``cat [-n] FILE...``."""

    name = "cat"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Concatenate files, optionally numbering lines across all of them."""
        numbered, files = _parse_cat_args(args)
        texts, errors = _read_files("cat", files, ctx)
        text = "".join(texts)
        body = text.removesuffix("\n")
        return CommandResult(
            output=_number_lines(body) if numbered else body,
            error="\n".join(errors),
            exit_code=EXIT_FAILURE if errors else EXIT_OK,
        )


def _tac_records(text: str) -> list[str]:
    r"""Split like GNU tac: "a\nb" -> ["a\n", "b"] (newline stays attached)."""
    if text == "":
        return []
    parts = text.split("\n")
    if parts[-1] == "":
        return [p + "\n" for p in parts[:-1]]
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


def _tac(text: str) -> str:
    return "".join(reversed(_tac_records(text)))


class TacCommand(Command):
    """``tac FILE...``, lines in reverse order."""

    name = "tac"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Print each file's lines in reverse order."""
        for arg in args:
            if arg.startswith("-") and len(arg) > 1:
                raise CommandArgsError(f"tac: invalid option -- '{arg[1]}'")
        if not args:
            raise CommandArgsError("tac: missing file operand")

        texts, errors = _read_files("tac", args, ctx)
        output = "".join(_tac(text) for text in texts)
        return CommandResult(
            output=output.removesuffix("\n"),
            error="\n".join(errors),
            exit_code=EXIT_FAILURE if errors else EXIT_OK,
        )


def _walk(node: VNode) -> Iterator[VNode]:
    """Yield the node and everything below it (for ``-R``)."""
    yield node
    if isinstance(node, VDir):
        for child in node.children.values():
            yield from _walk(child)


def _resolve_targets(
    cmd: str, paths: list[str], ctx: CommandContext, *, recursive: bool
) -> tuple[list[VNode], list[str]]:
    """Resolve chmod/chown operands -> (nodes, error lines).

    Bad paths only go to errors, the rest still get changed.
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


def _check_operands(cmd: str, spec: str | None, paths: list[str]) -> str:
    """Make sure chmod/chown got both the spec and at least one file."""
    if spec is None:
        raise CommandArgsError(f"{cmd}: missing operand")
    if not paths:
        raise CommandArgsError(f"{cmd}: missing operand after '{spec}'")
    return spec


def _is_dash_mode(arg: str) -> bool:
    """Check if a dash argument is a MODE, not an option.

    GNU takes "-x" (even junk like "-wz") as MODE.
    """
    return arg[1] in _CHMOD_MODE_LETTERS or looks_like_symbolic_mode(arg)


def _parse_chmod_args(args: list[str]) -> tuple[bool, str, list[str]]:
    """Split ``chmod`` arguments -> (recursive, MODE, paths)."""
    recursive = False
    mode_spec: str | None = None
    paths: list[str] = []
    for arg in args:
        is_dash_option = arg.startswith("-") and len(arg) > 1
        if arg == "-R":
            recursive = True
        elif mode_spec is None and is_dash_option and _is_dash_mode(arg):
            mode_spec = arg
        elif is_dash_option:
            raise CommandArgsError(f"chmod: invalid option -- '{arg[1]}'")
        elif mode_spec is None:
            mode_spec = arg
        else:
            paths.append(arg)

    return recursive, _check_operands("chmod", mode_spec, paths), paths


class ChmodCommand(Command):
    """``chmod [-R] MODE FILE...``, changes nodes in memory only."""

    name = "chmod"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Apply MODE to every target node."""
        recursive, mode_spec, paths = _parse_chmod_args(args)
        try:
            parse_mode(mode_spec, 0)
        except ModeError:
            return CommandResult(
                error=f"chmod: invalid mode: '{mode_spec}'",
                exit_code=EXIT_FAILURE,
            )

        targets, errors = _resolve_targets(
            "chmod", paths, ctx, recursive=recursive
        )
        for node in targets:
            node.mode = parse_mode(mode_spec, node.mode)

        return CommandResult(
            error="\n".join(errors),
            exit_code=EXIT_FAILURE if errors else EXIT_OK,
        )


class _InvalidOwnerSpecError(Exception):
    """Bad OWNER[:GROUP]; the message is the text after ``chown: ``."""


def _valid_owner_name(name: str) -> bool:
    return bool(_OWNER_NAME_RE.fullmatch(name))


def _parse_owner_spec(spec: str) -> tuple[str | None, str | None]:
    """Parse OWNER[:GROUP] -> (owner, group), None meaning "don't touch".

    ``user:`` keeps the group as is (GNU would switch to the login group,
    there is no such thing here).
    """
    if ":" not in spec:
        if not _valid_owner_name(spec):
            raise _InvalidOwnerSpecError(f"invalid user: '{spec}'")
        return spec, None

    owner_part, group_part = spec.split(":", 1)
    if owner_part == "" and group_part == "":
        raise _InvalidOwnerSpecError(f"invalid user: '{spec}'")

    new_owner = None
    new_group = None
    if owner_part != "":
        if not _valid_owner_name(owner_part):
            raise _InvalidOwnerSpecError(f"invalid user: '{owner_part}'")
        new_owner = owner_part
    if group_part != "":
        if not _valid_owner_name(group_part):
            raise _InvalidOwnerSpecError(f"invalid group: '{group_part}'")
        new_group = group_part
    return new_owner, new_group


def _parse_chown_args(args: list[str]) -> tuple[bool, str, list[str]]:
    """Split ``chown`` arguments -> (recursive, OWNER[:GROUP], paths)."""
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

    return recursive, _check_operands("chown", owner_spec, paths), paths


class ChownCommand(Command):
    """``chown [-R] OWNER[:GROUP] FILE...``, changes nodes in memory only."""

    name = "chown"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Change owner and/or group of every target node."""
        recursive, owner_spec, paths = _parse_chown_args(args)
        try:
            new_owner, new_group = _parse_owner_spec(owner_spec)
        except _InvalidOwnerSpecError as exc:
            return CommandResult(error=f"chown: {exc}", exit_code=EXIT_FAILURE)

        targets, errors = _resolve_targets(
            "chown", paths, ctx, recursive=recursive
        )
        for node in targets:
            node.owner = new_owner or node.owner
            node.group = new_group or node.group

        return CommandResult(
            error="\n".join(errors),
            exit_code=EXIT_FAILURE if errors else EXIT_OK,
        )


class VfsInfoCommand(Command):
    """``vfs-info``: name and SHA-256 of the loaded VFS."""

    name = "vfs-info"

    def run(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """Print the VFS name and the SHA-256 of its XML."""
        if args:
            raise CommandArgsError("vfs-info: too many arguments")
        if not ctx.vfs.loaded:
            return CommandResult(
                error="vfs-info: no VFS loaded", exit_code=EXIT_FAILURE
            )
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
