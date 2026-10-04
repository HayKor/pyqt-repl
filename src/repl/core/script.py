from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .errors import ScriptError
from .shell import ExecResult, Shell


@dataclass
class ScriptStep:
    """One executed, non-blank, non-comment-only line of a startup script."""

    lineno: int
    line: str
    result: ExecResult


def load_script(path: Path) -> list[str]:
    """Read ``path`` as UTF-8 text and return its lines (no line endings).

    Raises ``ScriptError`` with a bash-styled message for a missing file, a
    directory, a permission error, or content that is not valid UTF-8.
    """
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
    """Return True for an empty/whitespace-only line or a comment-only line."""
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def iter_script(shell: Shell, lines: list[str]) -> Iterator[ScriptStep]:
    """Execute ``lines`` one by one through ``shell``, yielding a ``ScriptStep``.

    Blank and comment-only lines are skipped: they are neither echoed nor
    executed. Iteration stops right after the first step whose result has a
    non-zero exit code or requests ``should_exit`` (i.e. commands after an
    error or an ``exit`` are never run).
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
    """Format the bash-styled message printed when ``step`` aborts the script."""
    return f"repl: {path}: line {step.lineno}: aborted (exit code {step.result.exit_code})"
