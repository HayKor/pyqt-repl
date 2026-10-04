"""Terminal-like widget: output pane and input line with history."""

import html
from typing import override

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

_OUTPUT_STYLE = (
    "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; "
    "border: none; }"
)
_ERROR_COLOR = "#ff6b68"


class _HistoryLineEdit(QLineEdit):
    """Input line with Up/Down history."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history: list[str] = []
        self._index = 0

    def add_to_history(self, text: str) -> None:
        """Remember a non-empty line and reset the history cursor."""
        if text:
            self._history.append(text)
        self._index = len(self._history)

    @override
    def keyPressEvent(self, event) -> None:
        """Browse history with Up/Down, pass other keys on."""
        if event.key() == Qt.Key.Key_Up:
            if self._history and self._index > 0:
                self._index -= 1
                self.setText(self._history[self._index])
            return
        if event.key() == Qt.Key.Key_Down:
            if self._index < len(self._history) - 1:
                self._index += 1
                self.setText(self._history[self._index])
            else:
                self._index = len(self._history)
                self.clear()
            return
        super().keyPressEvent(event)


class TerminalWidget(QWidget):
    """Output pane plus a prompt and an input line."""

    command_entered = pyqtSignal(str)

    def __init__(self, prompt: str, parent: QWidget | None = None) -> None:
        """Build the widgets; ``prompt`` is shown left of the input."""
        super().__init__(parent)
        self._prompt = prompt

        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        self._output = QPlainTextEdit(self)
        self._output.setReadOnly(True)
        self._output.setFont(mono_font)
        self._output.setStyleSheet(_OUTPUT_STYLE)

        self._prompt_label = QLabel(prompt, self)
        self._prompt_label.setFont(mono_font)

        self._input = _HistoryLineEdit(self)
        self._input.setFont(mono_font)
        self._input.returnPressed.connect(self._on_return_pressed)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.addWidget(self._prompt_label)
        input_row.addWidget(self._input)

        layout = QVBoxLayout(self)
        layout.addWidget(self._output)
        layout.addLayout(input_row)

        self._input.setFocus()

    def set_prompt(self, prompt: str) -> None:
        """Change the prompt shown before the input and in echoes."""
        self._prompt = prompt
        self._prompt_label.setText(prompt)

    def output_text(self) -> str:
        """Whole output pane as plain text."""
        return self._output.toPlainText()

    def append_output(self, text: str) -> None:
        """Append normal output (nothing for empty text)."""
        if text:
            self._append_plain(text)

    def append_error(self, text: str) -> None:
        """Append error text in red (nothing for empty text)."""
        if text:
            escaped = html.escape(text).replace("\n", "<br>")
            self._output.appendHtml(
                f'<span style="color:{_ERROR_COLOR};">{escaped}</span>'
            )
            self._scroll_to_bottom()

    def submit(self, line: str) -> None:
        """Act as if the line was typed and pressing Enter (for tests)."""
        self._input.setText(line)
        self._on_return_pressed()

    def echo_command(self, line: str) -> None:
        """Show ``prompt + line``; script lines go through here too."""
        self._append_plain(f"{self._prompt}{line}")

    def _on_return_pressed(self) -> None:
        line = self._input.text()
        self.echo_command(line)
        self._input.add_to_history(line)
        self._input.clear()
        self.command_entered.emit(line)

    def _append_plain(self, text: str) -> None:
        self._output.appendPlainText(text)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        scrollbar = self._output.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())
