"""Tests for CLI argument parsing and the debug config lines."""

from pathlib import Path

import pytest

from repl.core.errors import EXIT_USAGE
from repl.core.config import AppConfig, format_config, parse_args


def test_no_arguments_gives_defaults() -> None:
    assert parse_args([]) == AppConfig(vfs_path=None, script_path=None)


def test_vfs_option() -> None:
    cfg = parse_args(["--vfs", "fs.xml"])
    assert cfg.vfs_path == Path("fs.xml")
    assert cfg.script_path is None


def test_script_option() -> None:
    cfg = parse_args(["--script", "scripts/startup/basic.repl"])
    assert cfg.script_path == Path("scripts/startup/basic.repl")
    assert cfg.vfs_path is None


def test_both_options() -> None:
    cfg = parse_args(["--vfs", "fs.xml", "--script", "run.repl"])
    assert cfg.vfs_path == Path("fs.xml")
    assert cfg.script_path == Path("run.repl")


def test_equals_sign_syntax() -> None:
    cfg = parse_args(["--vfs=fs.xml"])
    assert cfg.vfs_path == Path("fs.xml")


def test_unknown_flag_exits_with_code_2() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--nope"])
    assert exc_info.value.code == EXIT_USAGE


def test_script_without_value_exits_with_code_2() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--script"])
    assert exc_info.value.code == EXIT_USAGE


def test_help_exits_with_code_0() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--help"])
    assert exc_info.value.code == 0


def test_format_config_not_set() -> None:
    assert format_config(AppConfig()) == [
        "[config] vfs    = <not set>",
        "[config] script = <not set>",
    ]


def test_format_config_existing_path(tmp_path: Path) -> None:
    script = tmp_path / "s.repl"
    script.write_text("ls\n")
    lines = format_config(AppConfig(script_path=script))
    assert lines[1] == f"[config] script = {script.resolve()} (exists)"


def test_format_config_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.xml"
    lines = format_config(AppConfig(vfs_path=missing))
    assert lines[0] == f"[config] vfs    = {missing.resolve()} (not found)"


def test_format_config_both_fields(tmp_path: Path) -> None:
    vfs = tmp_path / "fs.xml"
    vfs.write_text("<fs/>")
    script = tmp_path / "missing.repl"
    lines = format_config(AppConfig(vfs_path=vfs, script_path=script))
    assert lines[0] == f"[config] vfs    = {vfs.resolve()} (exists)"
    assert lines[1] == f"[config] script = {script.resolve()} (not found)"
