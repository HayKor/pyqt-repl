import pytest

from repl.core.commands import CdCommand, ExitCommand, LsCommand
from repl.core.errors import CommandArgsError


def test_ls_no_args() -> None:
    result = LsCommand().run([])
    assert result.output == "ls: args=[]"
    assert result.exit_code == 0
    assert result.should_exit is False


def test_ls_prints_args() -> None:
    result = LsCommand().run(["-l", "/home/arthur"])
    assert result.output == "ls: args=['-l', '/home/arthur']"


def test_ls_accepts_combined_valid_options() -> None:
    result = LsCommand().run(["-la", "-h"])
    assert result.output == "ls: args=['-la', '-h']"


def test_ls_rejects_unknown_option() -> None:
    with pytest.raises(CommandArgsError, match=r"ls: invalid option -- 'z'"):
        LsCommand().run(["-z"])


def test_ls_rejects_unknown_option_within_combo() -> None:
    with pytest.raises(CommandArgsError, match=r"ls: invalid option -- 'x'"):
        LsCommand().run(["-lx"])


def test_cd_prints_args() -> None:
    result = CdCommand().run(["/tmp"])
    assert result.output == "cd: args=['/tmp']"


def test_cd_no_args() -> None:
    result = CdCommand().run([])
    assert result.output == "cd: args=[]"


def test_cd_too_many_arguments() -> None:
    with pytest.raises(CommandArgsError, match="cd: too many arguments"):
        CdCommand().run(["/tmp", "/home"])


def test_exit_no_args_defaults_to_last_exit_code() -> None:
    result = ExitCommand().run([], last_exit_code=5)
    assert result.should_exit is True
    assert result.exit_code == 5


def test_exit_no_args_defaults_to_zero() -> None:
    result = ExitCommand().run([])
    assert result.exit_code == 0
    assert result.should_exit is True


def test_exit_with_explicit_code() -> None:
    result = ExitCommand().run(["3"])
    assert result.exit_code == 3
    assert result.should_exit is True


def test_exit_non_numeric_argument() -> None:
    with pytest.raises(CommandArgsError, match="exit: abc: numeric argument required"):
        ExitCommand().run(["abc"])


def test_exit_too_many_arguments() -> None:
    with pytest.raises(CommandArgsError, match="exit: too many arguments"):
        ExitCommand().run(["1", "2"])
