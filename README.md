# PyQt GUI REPL w/ VFS

Учебный проект: эмулятор командной оболочки UNIX-подобной ОС с графическим
интерфейсом (PyQt6).

## Архитектура

Ядро оболочки (`src/repl/core/`) не импортирует Qt и не зависит от GUI —
его логика проверяется обычным `pytest` без дисплея:

- `core/parser.py` — токенизатор командной строки (кавычки, `\`, `$VAR`,
  `${VAR}`, `~`, `$?`);
- `core/commands.py` — команды-заглушки `ls`, `cd`, `exit` и их реестр;
- `core/shell.py` — `Shell.execute(line)`, связывает парсер и команды,
  превращает исключения в текст ошибки и код возврата (как в bash);
- `core/sysinfo.py` — имя пользователя/хоста для заголовка окна и приглашения.

GUI (`src/repl/ui/`) — это тонкий слой поверх ядра: `TerminalWidget` показывает
ленту вывода и строку ввода, `MainWindow` передаёт введённую строку в
`Shell.execute` и печатает результат.

## Запуск

Требуется Python 3.14 и [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
uv run repl
# или
uv run python -m repl
```

## Тесты

```bash
uv run pytest -q
```

Тесты ядра (`test_parser.py`, `test_commands.py`, `test_shell.py`) запускаются
без дисплея. GUI smoke-тест (`test_gui_smoke.py`) требует PyQt6 и офскрин-платформу
Qt (пропускается автоматически, если PyQt6 не установлен):

```bash
QT_QPA_PLATFORM=offscreen uv run pytest -q
```

## Структура проекта

```
src/repl/
├── __init__.py       # main() → app.run()
├── __main__.py        # python -m repl
├── app.py              # QApplication, MainWindow, exec()
├── core/                # чистый Python, без Qt
│   ├── errors.py
│   ├── sysinfo.py
│   ├── parser.py
│   ├── commands.py
│   └── shell.py
└── ui/
    ├── main_window.py
    └── terminal.py
tests/
├── test_parser.py
├── test_commands.py
├── test_shell.py
└── test_gui_smoke.py
```

