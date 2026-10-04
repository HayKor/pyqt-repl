"""Startup script loading and execution."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .errors import ScriptError
from .shell import ExecResult, Shell


@dataclass
class ScriptStep:
    """One executed script line and its result."""

    lineno: int
    line: str
    result: ExecResult


def load_script(path: Path) -> list[str]:
    """Read a UTF-8 script file into lines; raises ScriptError."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ScriptError(f"repl: {path}: No such file or directory") from None
    except IsADirectoryError:
        raise ScriptError(f"repl: {path}: Is a directory") from None
    except PermissionError:
        raise ScriptError(f"repl: {path}: Permission denied") from None
    except UnicodeDecodeError:
        raise ScriptError(f"repl: {path}: invalid UTF-8") from None
    return text.splitlines()


def is_blank_or_comment(line: str) -> bool:
    """Check if a line is skipped (blank or ``#`` comment)."""
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def iter_script(shell: Shell, lines: list[str]) -> Iterator[ScriptStep]:
    """Execute script lines one by one, yielding a step for each.

    Skips blanks and comments, stops after the first error or ``exit``.
    """
    for lineno, line in enumerate(lines, start=1):
        if is_blank_or_comment(line):
            continue
        result = shell.execute(line)
        step = ScriptStep(lineno=lineno, line=line, result=result)
        yield step
        if result.exit_code != 0 or result.should_exit:
            return


def abort_message(path: Path, step: ScriptStep) -> str:
    """Message shown when a script stops on a failing line."""
    code = step.result.exit_code
    return f"repl: {path}: line {step.lineno}: aborted (exit code {code})"
