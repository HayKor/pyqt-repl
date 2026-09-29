"""Command-line configuration: parsing and its debug representation.

This stage only accepts and reports the VFS and startup-script paths; the
VFS itself is not loaded here (that is stage 3's job). Contains no Qt
imports so ``parse_args`` can run before ``QApplication`` is created.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_LABEL_WIDTH = 6


@dataclass(frozen=True)
class AppConfig:
    """Immutable, fully-parsed application configuration."""

    vfs_path: Path | None = None
    script_path: Path | None = None


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the ``repl`` entry point."""
    parser = argparse.ArgumentParser(
        prog="repl",
        description="UNIX shell emulator with a GUI front-end.",
    )
    parser.add_argument(
        "--vfs",
        metavar="PATH",
        type=Path,
        default=None,
        help="path to the virtual file system image (not loaded until stage 3)",
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
    """Parse ``argv`` strictly (unknown flags raise ``SystemExit(2)``)."""
    parser = build_arg_parser()
    namespace = parser.parse_args(argv)
    return AppConfig(vfs_path=namespace.vfs, script_path=namespace.script)


def _describe_path(path: Path | None) -> str:
    if path is None:
        return "<not set>"
    status = "exists" if path.exists() else "not found"
    return f"{path.resolve()} ({status})"


def format_config(cfg: AppConfig) -> list[str]:
    """Format ``cfg`` as ``[config] ...`` debug lines, one per field."""
    return [
        f"[config] {'vfs':<{_LABEL_WIDTH}} = {_describe_path(cfg.vfs_path)}",
        f"[config] {'script':<{_LABEL_WIDTH}} = {_describe_path(cfg.script_path)}",
    ]
