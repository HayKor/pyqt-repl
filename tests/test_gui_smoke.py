"""Smoke tests of the Qt window (offscreen platform)."""

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from repl.core.config import AppConfig
from repl.core.sysinfo import hostname, username, window_title
from repl.ui.main_window import MainWindow

CUSTOM_EXIT = 3


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_window_title_uses_sysinfo(qapp: QApplication) -> None:
    window = MainWindow()
    assert window.windowTitle() == window_title()


def test_command_echo_and_output(qapp: QApplication) -> None:
    window = MainWindow()
    window.terminal.submit("ls -l /")
    text = window.terminal.output_text()
    assert f"{window._prompt()}ls -l /" in text
    assert "total 0" in text


def test_initial_prompt_is_root(qapp: QApplication) -> None:
    window = MainWindow()
    assert window._prompt() == f"{username()}@{hostname()}:/$ "


def test_prompt_updates_after_cd(qapp: QApplication) -> None:
    window = MainWindow(config=AppConfig(vfs_path=_VFS_DIR / "deep.xml"))
    window.terminal.submit("cd home")
    assert window._prompt() == f"{username()}@{hostname()}:/home$ "
    window.terminal.submit("ls")
    text = window.terminal.output_text()
    assert f"{window._prompt()}ls" in text
    assert "user" in text


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


def test_debug_lines_shown_without_config(qapp: QApplication) -> None:
    window = MainWindow()
    text = window.terminal.output_text()
    assert "[config] vfs    = <not set>" in text
    assert "[config] script = <not set>" in text


def test_debug_lines_shown_with_config(
    qapp: QApplication, tmp_path: Path
) -> None:
    vfs = tmp_path / "fs.xml"
    vfs.write_text("<fs/>")
    window = MainWindow(config=AppConfig(vfs_path=vfs))
    text = window.terminal.output_text()
    assert f"[config] vfs    = {vfs.resolve()} (exists)" in text
    assert "[config] script = <not set>" in text


def test_startup_script_runs_with_echo_and_output(
    qapp: QApplication, tmp_path: Path
) -> None:
    script = tmp_path / "basic.repl"
    script.write_text("# a comment\nls -l /\ncd /\n")
    window = MainWindow(config=AppConfig(script_path=script))

    window.run_startup_script()

    text = window.terminal.output_text()
    assert f"{window._prompt()}ls -l /" in text
    assert "total 0" in text
    assert f"{window._prompt()}cd /" in text
    assert "# a comment" not in text


def test_startup_script_error_aborts_and_skips_later_commands(
    qapp: QApplication, tmp_path: Path
) -> None:
    script = tmp_path / "with_error.repl"
    script.write_text("ls -l /\nfoo bar\nls -l /never/reached\n")
    window = MainWindow(config=AppConfig(script_path=script))
    window.show()

    window.run_startup_script()

    text = window.terminal.output_text()
    assert "repl: foo: command not found" in text
    assert f"repl: {script}: line 2: aborted (exit code 127)" in text
    assert "/never/reached" not in text
    assert (
        window.isVisible() is True
    )  # falls back to interactive mode, window stays open


def test_startup_script_missing_file_reports_error(
    qapp: QApplication, tmp_path: Path
) -> None:
    missing = tmp_path / "missing.repl"
    window = MainWindow(config=AppConfig(script_path=missing))

    window.run_startup_script()

    text = window.terminal.output_text()
    assert f"repl: {missing}: No such file or directory" in text


def test_startup_script_exit_closes_the_window(
    qapp: QApplication, tmp_path: Path
) -> None:
    script = tmp_path / "exit.repl"
    script.write_text(f"ls -l /\nexit {CUSTOM_EXIT}\n")
    window = MainWindow(config=AppConfig(script_path=script))
    window.show()

    window.run_startup_script()

    assert window.isVisible() is False
    assert window.shell.last_exit_code == CUSTOM_EXIT


_VFS_DIR = Path(__file__).resolve().parent.parent / "vfs"


def test_valid_vfs_loads_and_prints_summary(qapp: QApplication) -> None:
    window = MainWindow(config=AppConfig(vfs_path=_VFS_DIR / "deep.xml"))
    text = window.terminal.output_text()
    assert "[vfs] loaded 'deep' (11 dirs, 7 files)" in text
    assert window.shell.vfs.loaded is True
    assert window.shell.vfs.name == "deep"


def test_broken_vfs_reports_error_and_keeps_empty_vfs(
    qapp: QApplication,
) -> None:
    window = MainWindow(
        config=AppConfig(vfs_path=_VFS_DIR / "broken" / "wrong_root.xml")
    )
    text = window.terminal.output_text()
    assert "invalid format: root element must be <vfs>" in text
    assert window.shell.vfs.loaded is False


def test_missing_vfs_reports_error(qapp: QApplication, tmp_path: Path) -> None:
    missing = tmp_path / "missing.xml"
    window = MainWindow(config=AppConfig(vfs_path=missing))
    text = window.terminal.output_text()
    assert f"repl: vfs: {missing}: No such file or directory" in text
    assert window.shell.vfs.loaded is False


def test_no_vfs_path_prints_nothing_vfs_related(qapp: QApplication) -> None:
    window = MainWindow()
    text = window.terminal.output_text()
    assert "[vfs]" not in text
    assert window.shell.vfs.loaded is False


def test_vfs_info_command_in_window(qapp: QApplication) -> None:
    window = MainWindow(config=AppConfig(vfs_path=_VFS_DIR / "minimal.xml"))
    window.terminal.submit("vfs-info")
    text = window.terminal.output_text()
    assert "name: minimal" in text
    assert "sha256:" in text


def test_vfs_info_command_without_vfs_reports_error(qapp: QApplication) -> None:
    window = MainWindow()
    window.terminal.submit("vfs-info")
    text = window.terminal.output_text()
    assert "vfs-info: no VFS loaded" in text


def test_chmod_then_ls_l_shows_the_new_mode(qapp: QApplication) -> None:
    window = MainWindow(config=AppConfig(vfs_path=_VFS_DIR / "deep.xml"))
    window.terminal.submit("chmod 700 /home/user/docs/notes.txt")
    window.terminal.submit("ls -l /home/user/docs/notes.txt")
    text = window.terminal.output_text()
    assert "-rwx------ user user  " in text
