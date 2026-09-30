from pathlib import Path

import pytest

from repl.core.commands import CdCommand, CommandContext, ExitCommand, LsCommand, VfsInfoCommand
from repl.core.errors import CommandArgsError
from repl.core.vfs import VFS


def make_ctx(last_exit_code: int = 0, vfs: VFS | None = None, cwd: str = "/") -> CommandContext:
    return CommandContext(
        vfs=vfs if vfs is not None else VFS.empty(),
        cwd=cwd,
        last_exit_code=last_exit_code,
        env={},
    )


def test_ls_no_args() -> None:
    result = LsCommand().run([], make_ctx())
    assert result.output == "ls: args=[]"
    assert result.exit_code == 0
    assert result.should_exit is False


def test_ls_prints_args() -> None:
    result = LsCommand().run(["-l", "/home/arthur"], make_ctx())
    assert result.output == "ls: args=['-l', '/home/arthur']"


def test_ls_accepts_combined_valid_options() -> None:
    result = LsCommand().run(["-la", "-h"], make_ctx())
    assert result.output == "ls: args=['-la', '-h']"


def test_ls_rejects_unknown_option() -> None:
    with pytest.raises(CommandArgsError, match=r"ls: invalid option -- 'z'"):
        LsCommand().run(["-z"], make_ctx())


def test_ls_rejects_unknown_option_within_combo() -> None:
    with pytest.raises(CommandArgsError, match=r"ls: invalid option -- 'x'"):
        LsCommand().run(["-lx"], make_ctx())


def test_cd_prints_args() -> None:
    result = CdCommand().run(["/tmp"], make_ctx())
    assert result.output == "cd: args=['/tmp']"


def test_cd_no_args() -> None:
    result = CdCommand().run([], make_ctx())
    assert result.output == "cd: args=[]"


def test_cd_too_many_arguments() -> None:
    with pytest.raises(CommandArgsError, match="cd: too many arguments"):
        CdCommand().run(["/tmp", "/home"], make_ctx())


def test_exit_no_args_defaults_to_last_exit_code() -> None:
    result = ExitCommand().run([], make_ctx(last_exit_code=5))
    assert result.should_exit is True
    assert result.exit_code == 5


def test_exit_no_args_defaults_to_zero() -> None:
    result = ExitCommand().run([], make_ctx())
    assert result.exit_code == 0
    assert result.should_exit is True


def test_exit_with_explicit_code() -> None:
    result = ExitCommand().run(["3"], make_ctx())
    assert result.exit_code == 3
    assert result.should_exit is True


def test_exit_non_numeric_argument() -> None:
    with pytest.raises(CommandArgsError, match="exit: abc: numeric argument required"):
        ExitCommand().run(["abc"], make_ctx())


def test_exit_too_many_arguments() -> None:
    with pytest.raises(CommandArgsError, match="exit: too many arguments"):
        ExitCommand().run(["1", "2"], make_ctx())


def test_vfs_info_not_loaded() -> None:
    result = VfsInfoCommand().run([], make_ctx())
    assert result.output == ""
    assert result.error == "vfs-info: no VFS loaded"
    assert result.exit_code == 1


def test_vfs_info_loaded() -> None:
    vfs = VFS(name="demo", sha256="abc123", root=VFS.empty().root, source=Path("fs.xml"))
    result = VfsInfoCommand().run([], make_ctx(vfs=vfs))
    assert result.output == "name: demo\nsha256: abc123"
    assert result.error == ""
    assert result.exit_code == 0


def test_vfs_info_too_many_arguments() -> None:
    with pytest.raises(CommandArgsError, match="vfs-info: too many arguments"):
        VfsInfoCommand().run(["extra"], make_ctx())
