"""PyQt GUI shell emulator with an in-memory virtual file system."""

import sys


def main() -> None:
    """Parse CLI arguments, then start the GUI and exit with its code.

    Arguments are parsed before Qt is imported, so a bad flag just
    prints usage and exits.
    """
    from .core.config import parse_args

    cfg = parse_args(sys.argv[1:])

    from .app import run

    sys.exit(run(cfg))
