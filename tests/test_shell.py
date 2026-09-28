from repl.core.shell import Shell


def make_shell() -> Shell:
    return Shell(env={"HOME": "/home/arthur"})


def test_empty_line_is_noop() -> None:
    shell = make_shell()
    result = shell.execute("   ")
    assert result == shell.execute("")
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.should_exit is False


def test_ls_with_expansion() -> None:
    shell = make_shell()
    result = shell.execute("ls -l $HOME")
    assert result.stdout == "ls: args=['-l', '/home/arthur']"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert shell.last_exit_code == 0


def test_cd_too_many_arguments_from_plan_example() -> None:
    shell = make_shell()
    result = shell.execute("cd \"${HOME}/my dir\" '$HOME'")
    assert result.stderr == "cd: too many arguments"
    assert result.exit_code == 2
    assert shell.last_exit_code == 2


def test_cd_single_quoted_literal() -> None:
    shell = make_shell()
    result = shell.execute("cd '$HOME'")
    assert result.stdout == "cd: args=['$HOME']"
    assert result.exit_code == 0


def test_ls_invalid_option() -> None:
    shell = make_shell()
    result = shell.execute("ls -z")
    assert result.stderr == "ls: invalid option -- 'z'"
    assert result.exit_code == 2
    assert shell.last_exit_code == 2


def test_unknown_command() -> None:
    shell = make_shell()
    result = shell.execute("foo bar")
    assert result.stderr == "repl: foo: command not found"
    assert result.exit_code == 127
    assert shell.last_exit_code == 127


def test_unterminated_quote_syntax_error() -> None:
    shell = make_shell()
    result = shell.execute('echo "unterminated')
    assert result.stderr == "repl: syntax error: unterminated double quote"
    assert result.exit_code == 2


def test_exit_non_numeric() -> None:
    shell = make_shell()
    result = shell.execute("exit abc")
    assert result.stderr == "exit: abc: numeric argument required"
    assert result.exit_code == 2
    assert result.should_exit is False


def test_exit_bare_uses_last_exit_code() -> None:
    shell = make_shell()
    shell.execute("ls -z")  # sets last_exit_code to 2
    result = shell.execute("exit")
    assert result.should_exit is True
    assert result.exit_code == 2


def test_exit_with_explicit_code() -> None:
    shell = make_shell()
    result = shell.execute("exit 7")
    assert result.should_exit is True
    assert result.exit_code == 7


def test_status_variable_expansion() -> None:
    shell = make_shell()
    shell.execute("ls -z")  # last_exit_code becomes 2
    result = shell.execute('ls "code=$?"')
    assert result.stdout == "ls: args=['code=2']"
