import sys

from PyQt6.QtWidgets import QApplication

from .core.config import AppConfig, format_config
from .ui.main_window import MainWindow


def run(config: AppConfig | None = None) -> int:
    cfg = config if config is not None else AppConfig()
    # flush or it sits in the buffer while the event loop runs (not a tty)
    print(*format_config(cfg), sep="\n", flush=True)

    app = QApplication([sys.argv[0]])
    window = MainWindow(config=cfg)
    window.show()
    return app.exec()
