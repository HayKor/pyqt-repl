"""The application's main window: wires the terminal widget to the shell."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from ..core.shell import Shell
from ..core.sysinfo import hostname, username, window_title
from .terminal import TerminalWidget


class MainWindow(QMainWindow):
    def __init__(self, shell: Shell | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.shell = shell if shell is not None else Shell()

        self.setWindowTitle(window_title())
        self.resize(800, 480)

        self.terminal = TerminalWidget(prompt=self._prompt())
        self.setCentralWidget(self.terminal)
        self.terminal.command_entered.connect(self._on_command)

    @staticmethod
    def _prompt() -> str:
        return f"{username()}@{hostname()}:~$ "

    def _on_command(self, line: str) -> None:
        result = self.shell.execute(line)

        if result.stdout:
            self.terminal.append_output(result.stdout)
        if result.stderr:
            self.terminal.append_error(result.stderr)

        if result.should_exit:
            app = QApplication.instance()
            if app is not None:
                app.exit(result.exit_code)
            self.close()
