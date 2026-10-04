"""Main window of the emulator."""

from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from ..core.config import AppConfig, format_config
from ..core.errors import ScriptError, VFSLoadError
from ..core.script import abort_message, iter_script, load_script
from ..core.shell import ExecResult, Shell
from ..core.sysinfo import hostname, username, window_title
from ..core.vfs_loader import describe, load_vfs
from .terminal import TerminalWidget


class MainWindow(QMainWindow):
    """Main window: terminal widget wired to a Shell."""

    def __init__(
        self,
        shell: Shell | None = None,
        config: AppConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Set up the terminal, print debug lines, load VFS, queue script."""
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

        if self.config.vfs_path is not None:
            self._load_vfs(self.config.vfs_path)

        if self.config.script_path is not None:
            QTimer.singleShot(0, self.run_startup_script)

    def _prompt(self) -> str:
        return f"{username()}@{hostname()}:{self.shell.cwd}$ "

    def _load_vfs(self, path: Path) -> None:
        # on error the shell just keeps the empty vfs
        try:
            vfs = load_vfs(path)
        except VFSLoadError as exc:
            self.terminal.append_error(str(exc))
            return
        self.shell.vfs = vfs
        self.terminal.append_output(describe(vfs))

    def _on_command(self, line: str) -> None:
        result = self.shell.execute(line)
        self._show_result(result)
        self.terminal.set_prompt(self._prompt())
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
        """Run ``--script`` line by line, echoing each like typed input.

        Public so tests can call it directly; normally a QTimer does.
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
            self.terminal.set_prompt(self._prompt())

        if last_step is None:
            return
        if last_step.result.should_exit:
            self._exit_app(last_step.result.exit_code)
        elif last_step.result.exit_code != 0:
            self.terminal.append_error(abort_message(path, last_step))
