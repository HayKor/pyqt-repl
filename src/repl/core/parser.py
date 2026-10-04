"""Command-line tokenizer: quotes, escapes, variables and comments."""

from collections.abc import Mapping
import os

from .errors import ParseError

_NAME_START = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
_NAME_CONT = _NAME_START | frozenset("0123456789")


def _expand_var(
    line: str, dollar_index: int, env: Mapping[str, str]
) -> tuple[str, int]:
    """Expand the variable at ``line[dollar_index]`` ('$').

    Returns (value, index right after the variable); a lone ``$`` stays as is.
    """
    j = dollar_index + 1
    nxt = line[j : j + 1]
    if nxt == "{":
        end = line.find("}", j + 1)
        if end == -1:
            raise ParseError("repl: syntax error: missing closing '}'")
        return env.get(line[j + 1 : end], ""), end + 1
    if nxt == "?":
        return env.get("?", ""), j + 1
    if nxt and nxt in _NAME_START:
        k = j + 1
        while k < len(line) and line[k] in _NAME_CONT:
            k += 1
        return env.get(line[j:k], ""), k
    return "$", j


def _read_single(line: str, i: int) -> tuple[str, int]:
    """Read a '...' string starting at the opening quote; no expansion."""
    end = line.find("'", i + 1)
    if end == -1:
        raise ParseError("repl: syntax error: unterminated single quote")
    return line[i + 1 : end], end + 1


def _read_double(line: str, i: int, env: Mapping[str, str]) -> tuple[str, int]:
    """Read a "..." string starting at the opening quote.

    Expands ``$VAR``; a backslash escapes only ``"``, backslash and ``$``.
    """
    n = len(line)
    i += 1
    buf: list[str] = []
    while i < n and line[i] != '"':
        if line[i] == "\\" and i + 1 < n and line[i + 1] in '"\\$':
            buf.append(line[i + 1])
            i += 2
        elif line[i] == "$":
            expanded, i = _expand_var(line, i, env)
            buf.append(expanded)
        else:
            buf.append(line[i])
            i += 1
    if i >= n:
        raise ParseError("repl: syntax error: unterminated double quote")
    return "".join(buf), i + 1


def _read_plain(line: str, i: int) -> tuple[str, int]:
    """Read one unquoted character, honouring a backslash escape."""
    if line[i] != "\\":
        return line[i], i + 1
    if i + 1 < len(line):
        return line[i + 1], i + 2
    return "\\", i + 1


def _read_word(
    line: str, i: int, env: Mapping[str, str]
) -> tuple[str, bool, int]:
    """Read one word up to whitespace -> (word, had_quotes, next index)."""
    n = len(line)
    parts: list[str] = []
    quoted = False
    while i < n and not line[i].isspace():
        c = line[i]
        if c == "'":
            piece, i = _read_single(line, i)
            quoted = True
        elif c == '"':
            piece, i = _read_double(line, i, env)
            quoted = True
        elif c == "$":
            piece, i = _expand_var(line, i, env)
        elif c == "~" and not parts:
            piece, i = env.get("HOME", ""), i + 1
        else:
            piece, i = _read_plain(line, i)
        parts.append(piece)
    return "".join(parts), quoted, i


def tokenize(line: str, env: Mapping[str, str] | None = None) -> list[str]:
    """Split a command line into words like a (very small) POSIX shell.

    Handles quotes, backslash escapes, ``$VAR``/``${VAR}``/``$?``, a leading
    ``~`` and ``#`` comments at the start of a word. Raises ParseError on
    unterminated quotes or ``${``.
    """
    if env is None:
        env = os.environ
    n = len(line)
    tokens: list[str] = []
    i = 0
    while i < n:
        while i < n and line[i].isspace():
            i += 1
        if i >= n or line[i] == "#":
            break
        word, quoted, i = _read_word(line, i, env)
        if quoted or word:
            tokens.append(word)
    return tokens
