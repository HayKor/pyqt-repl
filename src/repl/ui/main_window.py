"""The application's main window: wires the terminal widget to the shell."""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from ..core.config import AppConfig, format_config
from ..core.errors import ScriptError
from ..core.script import abort_message, iter_script, load_script
from ..core.shell import ExecResult, Shell
from ..core.sysinfo import hostname, username, window_title
from .terminal import TerminalWidget


class MainWindow(QMainWindow):
    def __init__(
        self,
        shell: Shell | None = None,
        config: AppConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.shell = shell if shell is not None else Shell()
        self.config = config if config is not None else AppConfig()

        self.setWindowTitle(window_title())
        self.resize(800, 480)

        self.terminal = TerminalWidget(prompt=self._prompt())
        self.setCentralWidget(self.terminal)
        self.terminal.command_entered.connect(self._on_command)

        for debug_line in format_config(self.config):
            self.terminal.append_output(debug_line)

        if self.config.script_path is not None:
            QTimer.singleShot(0, self.run_startup_script)

    @staticmethod
    def _prompt() -> str:
        return f"{username()}@{hostname()}:~$ "

    def _on_command(self, line: str) -> None:
        result = self.shell.execute(line)
        self._show_result(result)
        if result.should_exit:
            self._exit_app(result.exit_code)

    def _show_result(self, result: ExecResult) -> None:
        if result.stdout:
            self.terminal.append_output(result.stdout)
        if result.stderr:
            self.terminal.append_error(result.stderr)

    def _exit_app(self, exit_code: int) -> None:
        app = QApplication.instance()
        if app is not None:
            app.exit(exit_code)
        self.close()

    def run_startup_script(self) -> None:
        """Load and run ``self.config.script_path`` line by line.

        Public (rather than a private slot only reachable through
        ``QTimer.singleShot``) so tests can invoke it synchronously; the
        timer set up in ``__init__`` only calls it once the window is shown.
        On a load error the message is shown in red and the window falls
        back to ordinary interactive mode. On abort (a step with a non-zero
        exit code) ``abort_message`` is shown in red; on ``exit`` the window
        closes with that exit code, exactly like the interactive ``exit``
        command.
        """
        path = self.config.script_path
        if path is None:
            return

        try:
            lines = load_script(path)
        except ScriptError as exc:
            self.terminal.append_error(str(exc))
            return

        last_step = None
        for last_step in iter_script(self.shell, lines):
            self.terminal.echo_command(last_step.line)
            self._show_result(last_step.result)

        if last_step is None:
            return
        if last_step.result.should_exit:
            self._exit_app(last_step.result.exit_code)
        elif last_step.result.exit_code != 0:
            self.terminal.append_error(abort_message(path, last_step))
