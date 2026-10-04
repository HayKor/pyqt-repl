import sys


def main() -> None:
    from .core.config import parse_args

    # Parsed strictly before QApplication exists: a bad flag exits(2) with
    # the usual argparse ``usage: ...`` message and never opens a window.
    cfg = parse_args(sys.argv[1:])

    from .app import run

    sys.exit(run(cfg))
