"""GUI smoke test: run offscreen (QT_QPA_PLATFORM=offscreen), skipped if PyQt6
is not installed.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from repl.core.sysinfo import window_title  # noqa: E402
from repl.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_window_title_uses_sysinfo(qapp: QApplication) -> None:
    window = MainWindow()
    assert window.windowTitle() == window_title()


def test_command_echo_and_output(qapp: QApplication) -> None:
    window = MainWindow()
    window.terminal.submit("ls -l /tmp")
    text = window.terminal.output_text()
    assert f"{window._prompt()}ls -l /tmp" in text
    assert "ls: args=['-l', '/tmp']" in text


def test_unknown_command_reports_error(qapp: QApplication) -> None:
    window = MainWindow()
    window.terminal.submit("foo bar")
    text = window.terminal.output_text()
    assert "repl: foo: command not found" in text


def test_syntax_error_is_reported(qapp: QApplication) -> None:
    window = MainWindow()
    window.terminal.submit('echo "unterminated')
    text = window.terminal.output_text()
    assert "repl: syntax error: unterminated double quote" in text


def test_exit_closes_the_window(qapp: QApplication) -> None:
    window = MainWindow()
    window.show()
    assert window.isVisible() is True

    window.terminal.submit("exit")

    assert window.isVisible() is False
    assert window.shell.last_exit_code == 0
