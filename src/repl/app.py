import sys

from PyQt6.QtWidgets import QApplication

from .core.config import AppConfig, format_config
from .ui.main_window import MainWindow


def run(config: AppConfig | None = None) -> int:
    cfg = config if config is not None else AppConfig()
    # Flushed explicitly: stdout is block-buffered when not a tty, and the
    # event loop below can run indefinitely (e.g. no startup script), which
    # would otherwise delay this debug output forever.
    print(*format_config(cfg), sep="\n", flush=True)

    app = QApplication([sys.argv[0]])
    window = MainWindow(config=cfg)
    window.show()
    return app.exec()
