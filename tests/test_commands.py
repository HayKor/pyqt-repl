"""Tests for built-in commands over a hand-built VFS."""

import stat
import hashlib
from pathlib import Path

import pytest

from repl.core.commands import (
    CatCommand,
    CdCommand,
    ChmodCommand,
    ChownCommand,
    CommandContext,
    ExitCommand,
    LsCommand,
    TacCommand,
    VfsInfoCommand,
)
from repl.core.errors import EXIT_USAGE, CommandArgsError
from repl.core.shell import Shell
from repl.core.vfs import VDir, VFile, VFS, VNode
from repl.core.vfs_loader import load_vfs

CUSTOM_EXIT = 3


def perms(mode: int) -> str:
    """Render permission bits like ``ls -l`` does: ``rwxr-xr-x``."""
    return stat.filemode(mode)[1:]


def _file(
    name: str, data: bytes, owner: str = "root", mode: int = 0o644
) -> VFile:
    """Build a file node; group equals owner."""
    return VFile(name=name, mode=mode, owner=owner, group=owner, data=data)


def _dir(
    name: str, children: list[VNode], owner: str = "root", mode: int = 0o755
) -> VDir:
    """Build a directory node from a list of children; group equals owner."""
    return VDir(
        name=name,
        mode=mode,
        owner=owner,
        group=owner,
        children={child.name: child for child in children},
    )


def make_vfs() -> VFS:
    """Build the test tree.

    Has hidden files, an empty file and dir, a big file for ``-h`` and files
    without a trailing newline.
    """
    docs = _dir(
        "docs",
        [
            _file("notes.txt", b"ab\ncd\n", "user"),
            _file("empty.txt", b"", "user"),
        ],
        "user",
    )
    user = _dir("user", [docs, _file(".profile", b"xy", "user")], "user")
    logs = _dir(
        "logs",
        [
            _file("one.log", b"1\n2\n"),
            _file("two.log", b"3\n4"),
            _file("ab.txt", b"a\nb"),
        ],
    )
    root = _dir(
        "",
        [
            _dir("home", [user]),
            _dir("etc", [_file("motd.txt", b"z\n")]),
            _dir("var", [_file("big.log", b"x" * 1536), logs]),
            _dir("tmp", [], mode=0o777),
            _dir("bin", [_file("tool", b"AB", mode=0o755)]),
        ],
    )
    return VFS(name="test", sha256="deadbeef", root=root)


def make_ctx(
    last_exit_code: int = 0,
    vfs: VFS | None = None,
    cwd: str = "/",
    oldpwd: str | None = None,
) -> CommandContext:
    return CommandContext(
        vfs=vfs if vfs is not None else make_vfs(),
        cwd=cwd,
        last_exit_code=last_exit_code,
        env={},
        oldpwd=oldpwd,
    )


# ls


def test_ls_no_args_lists_cwd() -> None:
    result = LsCommand().run([], make_ctx(cwd="/home/user/docs"))
    assert result.output == "empty.txt  notes.txt"
    assert result.error == ""
    assert result.exit_code == 0


def test_ls_hides_dotfiles_without_a() -> None:
    result = LsCommand().run([], make_ctx(cwd="/home/user"))
    assert result.output == "docs"


def test_ls_a_shows_dot_entries_and_hidden_files() -> None:
    result = LsCommand().run(["-a"], make_ctx(cwd="/home/user"))
    assert result.output == ".  ..  .profile  docs"


def test_ls_l_format_with_total_and_alignment() -> None:
    result = LsCommand().run(["-l"], make_ctx(cwd="/home/user/docs"))
    assert result.output == (
        "total 2\n"
        "-rw-r--r-- user user  0 empty.txt\n"
        "-rw-r--r-- user user  6 notes.txt"
    )


def test_ls_l_on_root_shows_directory_modes_and_size_4096() -> None:
    result = LsCommand().run(["-l"], make_ctx(cwd="/"))
    assert result.output == (
        "total 5\n"
        "drwxr-xr-x root root  4096 bin\n"
        "drwxr-xr-x root root  4096 etc\n"
        "drwxr-xr-x root root  4096 home\n"
        "drwxrwxrwx root root  4096 tmp\n"
        "drwxr-xr-x root root  4096 var"
    )


def test_ls_lh_formats_large_file_as_human_size() -> None:
    result = LsCommand().run(["-lh"], make_ctx(cwd="/var"))
    assert "-rw-r--r-- root root  1.5K big.log" in result.output.splitlines()


def test_ls_lh_formats_directory_size_as_human_size() -> None:
    result = LsCommand().run(["-lh"], make_ctx(cwd="/"))
    assert "drwxr-xr-x root root  4.0K bin" in result.output.splitlines()


def test_ls_h_without_l_is_ignored() -> None:
    result = LsCommand().run(["-h"], make_ctx(cwd="/home/user/docs"))
    assert result.output == "empty.txt  notes.txt"


def test_ls_single_file_path_short_format() -> None:
    result = LsCommand().run(["/etc/motd.txt"], make_ctx())
    assert result.output == "/etc/motd.txt"
    assert result.exit_code == 0


def test_ls_single_file_path_long_format_has_no_total() -> None:
    result = LsCommand().run(["-l", "/etc/motd.txt"], make_ctx())
    assert result.output == "-rw-r--r-- root root  2 /etc/motd.txt"


def test_ls_multiple_paths_files_then_dirs_with_headers() -> None:
    result = LsCommand().run(["/etc/motd.txt", "/tmp"], make_ctx())
    assert result.output == "/etc/motd.txt\n\n/tmp:"


def test_ls_multiple_directories_each_get_a_header() -> None:
    result = LsCommand().run(["/etc", "/tmp"], make_ctx())
    assert result.output == "/etc:\nmotd.txt\n\n/tmp:"


def test_ls_cannot_access_missing_path() -> None:
    result = LsCommand().run(["/nope"], make_ctx())
    assert result.output == ""
    assert (
        result.error == "ls: cannot access '/nope': No such file or directory"
    )
    assert result.exit_code == EXIT_USAGE


def test_ls_cannot_access_not_a_directory() -> None:
    result = LsCommand().run(["/etc/motd.txt/x"], make_ctx())
    assert (
        result.error == "ls: cannot access '/etc/motd.txt/x': Not a directory"
    )
    assert result.exit_code == EXIT_USAGE


def test_ls_errors_do_not_abort_other_paths() -> None:
    result = LsCommand().run(["/nope", "/etc/motd.txt"], make_ctx())
    assert result.output == "/etc/motd.txt"
    assert (
        result.error == "ls: cannot access '/nope': No such file or directory"
    )
    assert result.exit_code == EXIT_USAGE


def test_ls_rejects_unknown_option() -> None:
    with pytest.raises(CommandArgsError, match=r"ls: invalid option -- 'z'"):
        LsCommand().run(["-z"], make_ctx())


def test_ls_rejects_unknown_option_within_combo() -> None:
    with pytest.raises(CommandArgsError, match=r"ls: invalid option -- 'x'"):
        LsCommand().run(["-lx"], make_ctx())


# cd


def test_cd_no_args_goes_to_root() -> None:
    ctx = make_ctx(cwd="/home/user/docs")
    result = CdCommand().run([], ctx)
    assert ctx.cwd == "/"
    assert ctx.oldpwd == "/home/user/docs"
    assert result.output == ""
    assert result.exit_code == 0


def test_cd_into_relative_subdir() -> None:
    ctx = make_ctx(cwd="/")
    CdCommand().run(["home/user"], ctx)
    assert ctx.cwd == "/home/user"
    assert ctx.oldpwd == "/"


def test_cd_dot_dot() -> None:
    ctx = make_ctx(cwd="/home/user/docs")
    CdCommand().run([".."], ctx)
    assert ctx.cwd == "/home/user"


def test_cd_nonexistent_path() -> None:
    ctx = make_ctx(cwd="/")
    result = CdCommand().run(["/nope"], ctx)
    assert result.error == "cd: /nope: No such file or directory"
    assert result.exit_code == 1
    assert ctx.cwd == "/"


def test_cd_into_a_file_is_not_a_directory() -> None:
    ctx = make_ctx(cwd="/")
    result = CdCommand().run(["/etc/motd.txt"], ctx)
    assert result.error == "cd: /etc/motd.txt: Not a directory"
    assert result.exit_code == 1
    assert ctx.cwd == "/"


def test_cd_dash_without_oldpwd() -> None:
    result = CdCommand().run(["-"], make_ctx(oldpwd=None))
    assert result.error == "cd: OLDPWD not set"
    assert result.exit_code == 1


def test_cd_dash_switches_to_oldpwd_and_prints_it() -> None:
    ctx = make_ctx(cwd="/home/user", oldpwd="/tmp")
    result = CdCommand().run(["-"], ctx)
    assert ctx.cwd == "/tmp"
    assert ctx.oldpwd == "/home/user"
    assert result.output == "/tmp"
    assert result.exit_code == 0


def test_cd_too_many_arguments() -> None:
    with pytest.raises(CommandArgsError, match="cd: too many arguments"):
        CdCommand().run(["/tmp", "/home"], make_ctx())


# exit


def test_exit_no_args_defaults_to_last_exit_code() -> None:
    result = ExitCommand().run([], make_ctx(last_exit_code=CUSTOM_EXIT))
    assert result.should_exit is True
    assert result.exit_code == CUSTOM_EXIT


def test_exit_no_args_defaults_to_zero() -> None:
    result = ExitCommand().run([], make_ctx())
    assert result.exit_code == 0
    assert result.should_exit is True


def test_exit_with_explicit_code() -> None:
    result = ExitCommand().run([str(CUSTOM_EXIT)], make_ctx())
    assert result.exit_code == CUSTOM_EXIT
    assert result.should_exit is True


def test_exit_non_numeric_argument() -> None:
    with pytest.raises(
        CommandArgsError, match="exit: abc: numeric argument required"
    ):
        ExitCommand().run(["abc"], make_ctx())


def test_exit_too_many_arguments() -> None:
    with pytest.raises(CommandArgsError, match="exit: too many arguments"):
        ExitCommand().run(["1", "2"], make_ctx())


# cat


def test_cat_concatenates_files_in_argument_order() -> None:
    result = CatCommand().run(
        ["/var/logs/one.log", "/var/logs/two.log"], make_ctx()
    )
    assert result.output == "1\n2\n3\n4"
    assert result.exit_code == 0


def test_cat_strips_one_trailing_newline() -> None:
    result = CatCommand().run(["/var/logs/one.log"], make_ctx())
    assert result.output == "1\n2"


def test_cat_n_numbers_lines_across_files() -> None:
    result = CatCommand().run(
        ["-n", "/var/logs/one.log", "/var/logs/two.log"], make_ctx()
    )
    assert result.output == "     1\t1\n     2\t2\n     3\t3\n     4\t4"


def test_cat_missing_file_reports_error_and_continues() -> None:
    result = CatCommand().run(["/nope", "/var/logs/one.log"], make_ctx())
    assert result.output == "1\n2"
    assert result.error == "cat: /nope: No such file or directory"
    assert result.exit_code == 1


def test_cat_directory_is_an_error() -> None:
    result = CatCommand().run(["/var"], make_ctx())
    assert result.output == ""
    assert result.error == "cat: /var: Is a directory"
    assert result.exit_code == 1


def test_cat_missing_file_operand() -> None:
    with pytest.raises(CommandArgsError, match="cat: missing file operand"):
        CatCommand().run([], make_ctx())


def test_cat_invalid_option() -> None:
    with pytest.raises(CommandArgsError, match=r"cat: invalid option -- 'x'"):
        CatCommand().run(["-x", "/var/logs/one.log"], make_ctx())


# tac


def test_tac_reverses_lines_within_a_file() -> None:
    result = TacCommand().run(["/var/logs/one.log"], make_ctx())
    assert result.output == "2\n1"


def test_tac_glues_last_unterminated_line_gnu_style() -> None:
    # GNU gives "ba\n" here, we just drop the trailing \n as usual
    result = TacCommand().run(["/var/logs/ab.txt"], make_ctx())
    assert result.output == "ba"


def test_tac_processes_each_file_independently_in_argument_order() -> None:
    result = TacCommand().run(
        ["/var/logs/two.log", "/var/logs/one.log"], make_ctx()
    )
    assert result.output == "43\n2\n1"


def test_tac_missing_file_reports_error_and_continues() -> None:
    result = TacCommand().run(["/nope", "/var/logs/one.log"], make_ctx())
    assert result.output == "2\n1"
    assert result.error == "tac: /nope: No such file or directory"
    assert result.exit_code == 1


def test_tac_directory_is_an_error() -> None:
    result = TacCommand().run(["/var"], make_ctx())
    assert result.output == ""
    assert result.error == "tac: /var: Is a directory"
    assert result.exit_code == 1


def test_tac_missing_file_operand() -> None:
    with pytest.raises(CommandArgsError, match="tac: missing file operand"):
        TacCommand().run([], make_ctx())


def test_tac_invalid_option() -> None:
    with pytest.raises(CommandArgsError, match=r"tac: invalid option -- 'x'"):
        TacCommand().run(["-x", "/var/logs/one.log"], make_ctx())


# chmod


def test_chmod_octal_sets_absolute_mode() -> None:
    ctx = make_ctx()
    result = ChmodCommand().run(["600", "/home/user/docs/notes.txt"], ctx)
    assert result.output == ""
    assert result.error == ""
    assert result.exit_code == 0
    assert (
        perms(ctx.vfs.resolve("/home/user/docs/notes.txt").mode) == "rw-------"
    )


def test_chmod_symbolic_single_clause() -> None:
    ctx = make_ctx()
    ChmodCommand().run(["u+x", "/home/user/docs/notes.txt"], ctx)
    assert (
        perms(ctx.vfs.resolve("/home/user/docs/notes.txt").mode) == "rwxr--r--"
    )


def test_chmod_symbolic_comma_list_with_equals() -> None:
    ctx = make_ctx()
    ChmodCommand().run(["u=rwx,g=rx,o=", "/home/user/docs/notes.txt"], ctx)
    assert (
        perms(ctx.vfs.resolve("/home/user/docs/notes.txt").mode) == "rwxr-x---"
    )


def test_chmod_dash_x_is_treated_as_mode_not_option() -> None:
    ctx = make_ctx()
    result = ChmodCommand().run(["-x", "/bin/tool"], ctx)
    assert result.exit_code == 0
    assert perms(ctx.vfs.resolve("/bin/tool").mode) == "rw-r--r--"


def test_chmod_recursive_applies_to_directory_and_descendants() -> None:
    ctx = make_ctx()
    ChmodCommand().run(["-R", "700", "/home/user/docs"], ctx)
    docs = ctx.vfs.resolve("/home/user/docs")
    assert perms(docs.mode) == "rwx------"
    assert perms(docs.children["notes.txt"].mode) == "rwx------"
    assert perms(docs.children["empty.txt"].mode) == "rwx------"


def test_chmod_missing_operand() -> None:
    with pytest.raises(CommandArgsError, match="chmod: missing operand"):
        ChmodCommand().run([], make_ctx())


def test_chmod_missing_operand_after_mode() -> None:
    with pytest.raises(
        CommandArgsError, match=r"chmod: missing operand after '755'"
    ):
        ChmodCommand().run(["755"], make_ctx())


def test_chmod_invalid_mode() -> None:
    result = ChmodCommand().run(
        ["xyz", "/home/user/docs/notes.txt"], make_ctx()
    )
    assert result.output == ""
    assert result.error == "chmod: invalid mode: 'xyz'"
    assert result.exit_code == 1


def test_chmod_cannot_access_reports_error_and_continues() -> None:
    ctx = make_ctx()
    result = ChmodCommand().run(
        ["600", "/nope", "/home/user/docs/notes.txt"], ctx
    )
    assert (
        result.error
        == "chmod: cannot access '/nope': No such file or directory"
    )
    assert result.exit_code == 1
    assert (
        perms(ctx.vfs.resolve("/home/user/docs/notes.txt").mode) == "rw-------"
    )


def test_chmod_rejects_unknown_option() -> None:
    with pytest.raises(CommandArgsError, match=r"chmod: invalid option -- 'z'"):
        ChmodCommand().run(
            ["-z", "600", "/home/user/docs/notes.txt"], make_ctx()
        )


def test_chmod_malformed_dash_mode_is_invalid_mode_not_option() -> None:
    result = ChmodCommand().run(
        ["-wz", "/home/user/docs/notes.txt"], make_ctx()
    )
    assert result.error == "chmod: invalid mode: '-wz'"
    assert result.exit_code == 1


# chown


def test_chown_user_only_changes_owner_leaves_group() -> None:
    ctx = make_ctx()
    result = ChownCommand().run(["alice", "/home/user/docs/notes.txt"], ctx)
    assert result.output == ""
    assert result.error == ""
    assert result.exit_code == 0
    node = ctx.vfs.resolve("/home/user/docs/notes.txt")
    assert node.owner == "alice"
    assert node.group == "user"


def test_chown_user_colon_group_sets_both() -> None:
    ctx = make_ctx()
    ChownCommand().run(["alice:staff", "/home/user/docs/notes.txt"], ctx)
    node = ctx.vfs.resolve("/home/user/docs/notes.txt")
    assert node.owner == "alice"
    assert node.group == "staff"


def test_chown_user_colon_leaves_group_unchanged() -> None:
    ctx = make_ctx()
    ChownCommand().run(["bob:", "/home/user/docs/notes.txt"], ctx)
    node = ctx.vfs.resolve("/home/user/docs/notes.txt")
    assert node.owner == "bob"
    assert node.group == "user"


def test_chown_colon_group_leaves_owner_unchanged() -> None:
    ctx = make_ctx()
    ChownCommand().run([":wheel", "/home/user/docs/notes.txt"], ctx)
    node = ctx.vfs.resolve("/home/user/docs/notes.txt")
    assert node.owner == "user"
    assert node.group == "wheel"


def test_chown_numeric_uid_and_gid() -> None:
    ctx = make_ctx()
    ChownCommand().run(["1000:1000", "/home/user/docs/notes.txt"], ctx)
    node = ctx.vfs.resolve("/home/user/docs/notes.txt")
    assert node.owner == "1000"
    assert node.group == "1000"


def test_chown_recursive_applies_to_directory_and_descendants() -> None:
    ctx = make_ctx()
    ChownCommand().run(["-R", "root:root", "/home/user/docs"], ctx)
    docs = ctx.vfs.resolve("/home/user/docs")
    assert docs.owner == "root"
    assert docs.group == "root"
    assert docs.children["notes.txt"].owner == "root"
    assert docs.children["empty.txt"].group == "root"


def test_chown_missing_operand() -> None:
    with pytest.raises(CommandArgsError, match="chown: missing operand"):
        ChownCommand().run([], make_ctx())


def test_chown_missing_operand_after_owner() -> None:
    with pytest.raises(
        CommandArgsError, match=r"chown: missing operand after 'alice'"
    ):
        ChownCommand().run(["alice"], make_ctx())


def test_chown_invalid_user() -> None:
    result = ChownCommand().run(
        ["Not-Valid!", "/home/user/docs/notes.txt"], make_ctx()
    )
    assert result.error == "chown: invalid user: 'Not-Valid!'"
    assert result.exit_code == 1


def test_chown_invalid_group() -> None:
    result = ChownCommand().run(
        ["alice:BAD!", "/home/user/docs/notes.txt"], make_ctx()
    )
    assert result.error == "chown: invalid group: 'BAD!'"
    assert result.exit_code == 1


def test_chown_bare_colon_is_invalid() -> None:
    result = ChownCommand().run([":", "/home/user/docs/notes.txt"], make_ctx())
    assert result.error == "chown: invalid user: ':'"
    assert result.exit_code == 1


def test_chown_cannot_access_reports_error_and_continues() -> None:
    ctx = make_ctx()
    result = ChownCommand().run(
        ["alice", "/nope", "/home/user/docs/notes.txt"], ctx
    )
    assert (
        result.error
        == "chown: cannot access '/nope': No such file or directory"
    )
    assert result.exit_code == 1
    assert ctx.vfs.resolve("/home/user/docs/notes.txt").owner == "alice"


def test_chown_rejects_unknown_option() -> None:
    with pytest.raises(CommandArgsError, match=r"chown: invalid option -- 'z'"):
        ChownCommand().run(
            ["-z", "alice", "/home/user/docs/notes.txt"], make_ctx()
        )


# chmod/chown don't write anything back to the xml


def test_chmod_and_chown_do_not_modify_the_vfs_source_file() -> None:
    path = Path(__file__).resolve().parent.parent / "vfs" / "deep.xml"
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    shell = Shell(vfs=load_vfs(path))
    shell.execute("chmod 700 /home/user/docs/notes.txt")
    shell.execute("chmod -R u+x /home/user")
    shell.execute("chown alice:staff /home/user/docs/notes.txt")
    shell.execute("chown -R root /home/user")

    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert after == before
    # hash is still the original file's
    assert shell.vfs.sha256 == before


# vfs-info


def test_vfs_info_not_loaded() -> None:
    result = VfsInfoCommand().run([], make_ctx(vfs=VFS.empty()))
    assert result.output == ""
    assert result.error == "vfs-info: no VFS loaded"
    assert result.exit_code == 1


def test_vfs_info_loaded() -> None:
    vfs = VFS(
        name="demo",
        sha256="abc123",
        root=VFS.empty().root,
        source=Path("fs.xml"),
    )
    result = VfsInfoCommand().run([], make_ctx(vfs=vfs))
    assert result.output == "name: demo\nsha256: abc123"
    assert result.error == ""
    assert result.exit_code == 0


def test_vfs_info_too_many_arguments() -> None:
    with pytest.raises(CommandArgsError, match="vfs-info: too many arguments"):
        VfsInfoCommand().run(["extra"], make_ctx())
