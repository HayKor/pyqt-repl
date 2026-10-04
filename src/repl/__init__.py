import sys


def main() -> None:
    from .core.config import parse_args

    # before Qt, so a bad flag just prints usage and exits
    cfg = parse_args(sys.argv[1:])

    from .app import run

    sys.exit(run(cfg))
