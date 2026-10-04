"""PyQt GUI shell emulator with an in-memory virtual file system."""

import sys


def main() -> None:
    """Parse CLI arguments, then start the GUI and exit with its code."""
    from .core.config import parse_args

    # before Qt, so a bad flag just prints usage and exits
    cfg = parse_args(sys.argv[1:])

    from .app import run

    sys.exit(run(cfg))
