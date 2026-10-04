"""Command-line options and their debug output."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_LABEL_WIDTH = 6


@dataclass(frozen=True)
class AppConfig:
    """Startup options from the command line (None means not given)."""

    vfs_path: Path | None = None
    script_path: Path | None = None


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``--vfs`` and ``--script``."""
    parser = argparse.ArgumentParser(
        prog="repl",
        description="UNIX shell emulator with a GUI front-end.",
    )
    parser.add_argument(
        "--vfs",
        metavar="PATH",
        type=Path,
        default=None,
        help="path to the virtual file system image (XML)",
    )
    parser.add_argument(
        "--script",
        metavar="PATH",
        type=Path,
        default=None,
        help="path to a startup script executed after the window opens",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> AppConfig:
    """Parse argv into AppConfig; argparse exits with code 2 on errors."""
    parser = build_arg_parser()
    namespace = parser.parse_args(argv)
    return AppConfig(vfs_path=namespace.vfs, script_path=namespace.script)


def _describe_path(path: Path | None) -> str:
    """Render a path for the debug output: absolute + exists/not found."""
    if path is None:
        return "<not set>"
    status = "exists" if path.exists() else "not found"
    return f"{path.resolve()} ({status})"


def format_config(cfg: AppConfig) -> list[str]:
    """Return the ``[config] ...`` debug lines printed at startup."""
    return [
        f"[config] {'vfs':<{_LABEL_WIDTH}} = {_describe_path(cfg.vfs_path)}",
        f"[config] {'script':<{_LABEL_WIDTH}} = "
        f"{_describe_path(cfg.script_path)}",
    ]
