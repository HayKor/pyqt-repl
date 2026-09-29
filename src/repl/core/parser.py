"""Command-line tokenizer with POSIX-sh-like quoting and env-var expansion.

Implemented as a small hand-written finite state machine rather than
``shlex``, because ``shlex`` does not expose which quoting style (if any)
wrapped a given fragment, and that information is required to decide
whether ``$VAR`` inside it should be expanded.

Supported subset:
    - unquoted whitespace separates words;
    - ``'...'``      literal, no expansion;
    - ``"..."``      ``$VAR`` / ``${VAR}`` are expanded; ``\\"``, ``\\\\``,
                      ``\\$`` are recognized escapes;
    - ``\\x``        outside quotes escapes a single character;
    - ``$NAME``      NAME matches ``[A-Za-z_][A-Za-z0-9_]*``; ``${NAME}``
                      is the braced form; an unknown variable expands to
                      the empty string; a lone ``$`` with no valid name
                      stays a literal ``$``;
    - ``$?``         expands via the same lookup (the shell layer supplies
                      it as the ``"?"`` key of the env mapping);
    - ``~``          at the very start of an unquoted word expands to
                      ``$HOME``;
    - ``#``          outside quotes, at the very start of a word, starts a
                      comment that runs to the end of the line (``ls -l #
                      comment``, ``# whole line``); ``#`` inside a word
                      (``a#b``) or inside quotes (``'#'``, ``"#"``) is a
                      literal character, and ``\\#`` escapes it;
    - an unterminated quote, or ``${`` without a matching ``}``, raises
      ``ParseError``;
    - a word built entirely from unquoted text that expands to the empty
      string is dropped, matching sh word-splitting; ``""`` still yields
      an empty argument.
"""

from __future__ import annotations

from collections.abc import Mapping
import os

from .errors import ParseError

_NAME_START = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
_NAME_CONT = _NAME_START | frozenset("0123456789")


def _expand_var(line: str, dollar_index: int, env: Mapping[str, str]) -> tuple[str, int]:
    """Expand the variable reference starting at ``line[dollar_index] == '$'``.

    Returns ``(expanded_text, next_index)``.
    """
    n = len(line)
    j = dollar_index + 1

    if j < n and line[j] == "{":
        k = j + 1
        start = k
        while k < n and line[k] != "}":
            k += 1
        if k >= n:
            raise ParseError("repl: syntax error: missing closing '}'")
        name = line[start:k]
        return env.get(name, ""), k + 1

    if j < n and line[j] == "?":
        return env.get("?", ""), j + 1

    if j < n and line[j] in _NAME_START:
        k = j + 1
        while k < n and line[k] in _NAME_CONT:
            k += 1
        name = line[j:k]
        return env.get(name, ""), k

    # No valid name follows: '$' is a literal character.
    return "$", j


def tokenize(line: str, env: Mapping[str, str] | None = None) -> list[str]:
    """Split ``line`` into argv-style words, expanding variables in ``env``."""
    if env is None:
        env = os.environ

    n = len(line)
    tokens: list[str] = []
    i = 0

    while i < n:
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            break

        if line[i] == "#":
            # Unquoted '#' at the start of a word: comment to end of line.
            break

        parts: list[str] = []
        quoted = False

        while i < n and not line[i].isspace():
            c = line[i]

            if c == "'":
                quoted = True
                i += 1
                start = i
                while i < n and line[i] != "'":
                    i += 1
                if i >= n:
                    raise ParseError("repl: syntax error: unterminated single quote")
                parts.append(line[start:i])
                i += 1

            elif c == '"':
                quoted = True
                i += 1
                buf: list[str] = []
                while i < n and line[i] != '"':
                    ch = line[i]
                    if ch == "\\" and i + 1 < n and line[i + 1] in ('"', "\\", "$"):
                        buf.append(line[i + 1])
                        i += 2
                        continue
                    if ch == "$":
                        expanded, i = _expand_var(line, i, env)
                        buf.append(expanded)
                        continue
                    buf.append(ch)
                    i += 1
                if i >= n:
                    raise ParseError("repl: syntax error: unterminated double quote")
                parts.append("".join(buf))
                i += 1

            elif c == "\\":
                if i + 1 < n:
                    parts.append(line[i + 1])
                    i += 2
                else:
                    parts.append("\\")
                    i += 1

            elif c == "$":
                expanded, i = _expand_var(line, i, env)
                parts.append(expanded)

            elif c == "~" and not parts:
                parts.append(env.get("HOME", ""))
                i += 1

            else:
                parts.append(c)
                i += 1

        word = "".join(parts)
        if not quoted and word == "":
            continue
        tokens.append(word)

    return tokens
