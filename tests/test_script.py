import os
from pathlib import Path

import pytest

from repl.core.errors import ScriptError
from repl.core.script import abort_message, is_blank_or_comment, iter_script, load_script
from repl.core.shell import Shell
from repl.core.vfs import VDir, VFS


def make_vfs() -> VFS:
    tmp = VDir(name="tmp", mode=0o755, owner="root", group="root", children={})
    zero = VDir(name="0", mode=0o755, owner="root", group="root", children={})
    root = VDir(
        name="", mode=0o755, owner="root", group="root", children={"tmp": tmp, "0": zero}
    )
    return VFS(name="test", sha256="deadbeef", root=root)


def make_shell() -> Shell:
    return Shell(env={"HOME": "/"}, vfs=make_vfs())


def test_is_blank_or_comment() -> None:
    assert is_blank_or_comment("") is True
    assert is_blank_or_comment("   ") is True
    assert is_blank_or_comment("# comment") is True
    assert is_blank_or_comment("   # comment") is True
    assert is_blank_or_comment("ls -l") is False
    assert is_blank_or_comment("ls -l # inline") is False


def test_iter_script_skips_blank_and_comment_lines() -> None:
    shell = make_shell()
    lines = ["# header", "", "ls -l $HOME", "  ", "cd /tmp"]
    steps = list(iter_script(shell, lines))
    assert [step.lineno for step in steps] == [3, 5]
    assert steps[0].result.stdout == (
        "total 2\ndrwxr-xr-x root root  4096 0\ndrwxr-xr-x root root  4096 tmp"
    )
    assert steps[1].result.stdout == ""
    assert steps[1].result.exit_code == 0


def test_iter_script_stops_on_first_error() -> None:
    shell = make_shell()
    lines = ["ls -l $HOME", "foo bar", "ls -l /never/reached"]
    steps = list(iter_script(shell, lines))
    assert len(steps) == 2
    assert steps[-1].line == "foo bar"
    assert steps[-1].result.exit_code == 127
    assert steps[-1].result.should_exit is False


def test_iter_script_stops_on_exit() -> None:
    shell = make_shell()
    lines = ["ls -l $HOME", "exit 3", "ls -l /never/reached"]
    steps = list(iter_script(shell, lines))
    assert len(steps) == 2
    assert steps[-1].result.should_exit is True
    assert steps[-1].result.exit_code == 3


def test_status_variable_carries_between_script_lines() -> None:
    shell = make_shell()
    lines = ["ls -l $HOME", 'cd "/$?"']
    steps = list(iter_script(shell, lines))
    assert len(steps) == 2
    # $? -> "0" so cd "/$?" landed in /0
    assert steps[1].result.exit_code == 0
    assert shell.cwd == "/0"


def test_abort_message_format() -> None:
    shell = make_shell()
    lines = ["ls -l $HOME", "foo bar"]
    steps = list(iter_script(shell, lines))
    message = abort_message(Path("scripts/startup/with_error.repl"), steps[-1])
    assert message == "repl: scripts/startup/with_error.repl: line 2: aborted (exit code 127)"


def test_load_script_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.repl"
    with pytest.raises(ScriptError, match="No such file or directory"):
        load_script(missing)


def test_load_script_directory(tmp_path: Path) -> None:
    with pytest.raises(ScriptError, match="Is a directory"):
        load_script(tmp_path)


def test_load_script_not_utf8(tmp_path: Path) -> None:
    path = tmp_path / "bad.repl"
    path.write_bytes(b"\xff\xfe\x00ls\n")
    with pytest.raises(ScriptError, match="invalid UTF-8"):
        load_script(path)


def test_load_script_reads_lines(tmp_path: Path) -> None:
    path = tmp_path / "s.repl"
    path.write_text("ls -l\ncd /tmp\n")
    assert load_script(path) == ["ls -l", "cd /tmp"]


@pytest.mark.skipif(
    os.name != "posix" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="permission bits are unreliable for root or on non-POSIX systems",
)
def test_load_script_permission_denied(tmp_path: Path) -> None:
    path = tmp_path / "no_perm.repl"
    path.write_text("ls\n")
    path.chmod(0)
    try:
        with pytest.raises(ScriptError, match="Permission denied"):
            load_script(path)
    finally:
        path.chmod(0o644)
