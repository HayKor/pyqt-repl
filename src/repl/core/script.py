from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .errors import ScriptError
from .shell import ExecResult, Shell


@dataclass
class ScriptStep:
    lineno: int
    line: str
    result: ExecResult


def load_script(path: Path) -> list[str]:
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
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def iter_script(shell: Shell, lines: list[str]) -> Iterator[ScriptStep]:
    # skips blanks/comments, stops after the first error or exit
    for lineno, line in enumerate(lines, start=1):
        if is_blank_or_comment(line):
            continue
        result = shell.execute(line)
        step = ScriptStep(lineno=lineno, line=line, result=result)
        yield step
        if result.exit_code != 0 or result.should_exit:
            return


def abort_message(path: Path, step: ScriptStep) -> str:
    return f"repl: {path}: line {step.lineno}: aborted (exit code {step.result.exit_code})"
