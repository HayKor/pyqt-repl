"""Tests for the command-line tokenizer."""

import pytest

from repl.core.errors import ParseError
from repl.core.parser import tokenize

ENV = {"HOME": "/home/arthur", "EMPTY": ""}


def test_simple_split() -> None:
    assert tokenize("ls -l /tmp", ENV) == ["ls", "-l", "/tmp"]


def test_extra_whitespace_is_ignored() -> None:
    assert tokenize("  ls   -l  ", ENV) == ["ls", "-l"]


def test_empty_line() -> None:
    assert tokenize("", ENV) == []
    assert tokenize("   ", ENV) == []


def test_dollar_var_expansion() -> None:
    assert tokenize("ls -l $HOME", ENV) == ["ls", "-l", "/home/arthur"]


def test_braced_var_expansion() -> None:
    assert tokenize('cd "${HOME}/my dir"', ENV) == ["cd", "/home/arthur/my dir"]


def test_unknown_var_expands_to_empty_and_word_dropped() -> None:
    assert tokenize("ls $NOPE", ENV) == ["ls"]


def test_unknown_var_inside_quotes_keeps_empty_word() -> None:
    assert tokenize('ls "$NOPE"', ENV) == ["ls", ""]


def test_single_quotes_are_literal() -> None:
    assert tokenize("cd '$HOME'", ENV) == ["cd", "$HOME"]


def test_double_quotes_expand() -> None:
    assert tokenize('echo "$HOME"', ENV) == ["echo", "/home/arthur"]


def test_double_quote_escapes() -> None:
    assert tokenize(r'echo "a\"b\\c\$d"', ENV) == ["echo", 'a"b\\c$d']


def test_backslash_outside_quotes_escapes_one_char() -> None:
    assert tokenize(r"echo a\ b", ENV) == ["echo", "a b"]


def test_lone_dollar_is_literal() -> None:
    assert tokenize("echo $", ENV) == ["echo", "$"]


def test_dollar_followed_by_digit_is_literal() -> None:
    assert tokenize("echo $1", ENV) == ["echo", "$1"]


def test_question_mark_status_expansion() -> None:
    assert tokenize("echo $?", {"?": "2"}) == ["echo", "2"]


def test_tilde_expands_at_start_of_word() -> None:
    assert tokenize("cd ~", ENV) == ["cd", "/home/arthur"]


def test_tilde_mid_word_is_literal() -> None:
    assert tokenize("echo a~b", ENV) == ["echo", "a~b"]


def test_tilde_inside_quotes_is_literal() -> None:
    assert tokenize("echo '~'", ENV) == ["echo", "~"]


def test_empty_quoted_word_is_kept() -> None:
    assert tokenize('echo ""', ENV) == ["echo", ""]


def test_adjacent_quoted_and_unquoted_parts_join() -> None:
    assert tokenize('echo foo"bar"baz', ENV) == ["echo", "foobarbaz"]


def test_full_plan_example() -> None:
    assert tokenize("ls -l $HOME", ENV) == ["ls", "-l", "/home/arthur"]
    assert tokenize("cd \"${HOME}/my dir\" '$HOME'", ENV) == [
        "cd",
        "/home/arthur/my dir",
        "$HOME",
    ]


def test_unterminated_single_quote_raises() -> None:
    with pytest.raises(ParseError):
        tokenize("echo 'unterminated", ENV)


def test_unterminated_double_quote_raises() -> None:
    with pytest.raises(ParseError):
        tokenize('echo "unterminated', ENV)


def test_unterminated_brace_raises() -> None:
    with pytest.raises(ParseError):
        tokenize("echo ${HOME", ENV)


def test_hash_comment_whole_line_is_dropped() -> None:
    assert tokenize("# only", ENV) == []


def test_hash_comment_after_command() -> None:
    assert tokenize("ls -l # comment", ENV) == ["ls", "-l"]


def test_hash_mid_word_is_literal() -> None:
    assert tokenize("echo a#b", ENV) == ["echo", "a#b"]


def test_hash_in_single_quotes_is_literal() -> None:
    assert tokenize("echo '#'", ENV) == ["echo", "#"]


def test_hash_in_double_quotes_is_literal() -> None:
    assert tokenize('echo "#"', ENV) == ["echo", "#"]


def test_escaped_hash_is_literal() -> None:
    assert tokenize(r"echo \#", ENV) == ["echo", "#"]
