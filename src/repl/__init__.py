"""Entry point package for the `repl` console script.

Qt is imported lazily inside ``main()`` so that ``repl.core`` (and anything
importing only from it) never requires PyQt6 to be installed.
"""

from __future__ import annotations

import sys


def main() -> None:
    from .core.config import parse_args

    # Parsed strictly before QApplication exists: a bad flag exits(2) with
    # the usual argparse ``usage: ...`` message and never opens a window.
    cfg = parse_args(sys.argv[1:])

    from .app import run

    sys.exit(run(cfg))
