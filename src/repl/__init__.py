"""Entry point package for the `repl` console script.

Qt is imported lazily inside ``main()`` so that ``repl.core`` (and anything
importing only from it) never requires PyQt6 to be installed.
"""

from __future__ import annotations

import sys


def main() -> None:
    from .app import run

    sys.exit(run())
