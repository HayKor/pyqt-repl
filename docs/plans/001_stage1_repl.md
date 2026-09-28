# План 001 — Этап 1: REPL (вариант №4, эмулятор командной оболочки)

## Цель

Минимальный GUI-прототип эмулятора UNIX-оболочки на PyQt6: диалог с пользователем,
парсер с раскрытием переменных окружения, команды-заглушки `ls`/`cd`, команда `exit`,
сообщения об ошибках.

## Требования этапа (из docs/task.pdf) → как закрываем

| # | Требование | Реализация |
|---|------------|------------|
| 1 | GUI | PyQt6, `QMainWindow` + собственный виджет терминала |
| 2 | Заголовок из реальных данных ОС | `getpass.getuser()` + `socket.gethostname()` → `Эмулятор - [user@host]` |
| 3 | Парсер с раскрытием `$HOME` и т.п. | Собственный токенизатор (конечный автомат), `$VAR`, `${VAR}`, кавычки, `\` |
| 4 | Ошибки: неизвестная команда, неверные аргументы | Иерархия исключений `ShellError`, вывод в стиле bash |
| 5 | Заглушки `ls`, `cd` выводят имя и аргументы | Классы команд в реестре |
| 6 | `exit` | Команда возвращает флаг выхода + код, GUI закрывает окно |
| 7 | Демонстрация | Раздел в README с примером сессии + smoke-тест в offscreen-режиме |
| 8 | Коммит | Conventional Commits: `feat(repl): ...` |

## 1. Архитектура проекта

Принцип: **ядро оболочки не зависит от Qt**. GUI только передаёт строку в ядро и печатает
результат. Это позволяет тестировать ядро pytest'ом без дисплея и переиспользовать его на
этапе 2 (стартовый скрипт) и этапе 3 (VFS).

```
conf-uprav-1/
├── pyproject.toml            # зависимость PyQt6, dev: pytest, entry point `repl`
├── README.md                 # запуск + пример сессии (демонстрация, п.7)
├── docs/
│   ├── task.pdf
│   └── plans/001_stage1_repl.md
├── src/repl/
│   ├── __init__.py           # main() → app.run()
│   ├── __main__.py           # `python -m repl`
│   ├── app.py                # создание QApplication, MainWindow, exec()
│   ├── core/                 # ЧИСТЫЙ Python, без импортов Qt
│   │   ├── __init__.py
│   │   ├── errors.py         # ShellError, ParseError, CommandNotFoundError, CommandArgsError
│   │   ├── sysinfo.py        # username(), hostname(), window_title()
│   │   ├── parser.py         # tokenize(line, env) -> list[str]
│   │   ├── commands.py       # Command (базовый), LsCommand, CdCommand, ExitCommand, REGISTRY
│   │   └── shell.py          # Shell.execute(line) -> ExecResult
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py    # MainWindow: заголовок, связывает Terminal ↔ Shell
│       └── terminal.py       # TerminalWidget: вывод + строка ввода с приглашением, история
└── tests/
    ├── test_parser.py
    ├── test_commands.py
    └── test_shell.py
```

### Поток данных

```
[QLineEdit] --returnPressed--> TerminalWidget.command_entered(str)  (pyqtSignal)
      ↓
MainWindow._on_command(line)
      ↓
Shell.execute(line) ── parser.tokenize ──> argv
      │                 REGISTRY[argv[0]].run(argv[1:])
      ↓
ExecResult(stdout: str, stderr: str, exit_code: int, should_exit: bool)
      ↓
TerminalWidget.append_output / append_error;  should_exit → window.close() / app.exit(code)
```

### Ключевые интерфейсы (core)

```python
# errors.py
class ShellError(Exception): ...                   # базовая, str(e) = готовое сообщение
class ParseError(ShellError): ...                  # "repl: syntax error: unterminated quote"
class CommandNotFoundError(ShellError): ...        # "repl: foo: command not found"
class CommandArgsError(ShellError): ...            # "cd: too many arguments"

# parser.py
def tokenize(line: str, env: Mapping[str, str] | None = None) -> list[str]
# env по умолчанию = os.environ

# commands.py
@dataclass
class CommandResult:
    output: str = ""
    exit_code: int = 0
    should_exit: bool = False

class Command(ABC):
    name: ClassVar[str]
    @abstractmethod
    def run(self, args: list[str]) -> CommandResult: ...   # бросает CommandArgsError

REGISTRY: dict[str, Command]   # {"ls": LsCommand(), "cd": CdCommand(), "exit": ExitCommand()}

# shell.py
@dataclass
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    should_exit: bool = False

class Shell:
    def __init__(self, env: Mapping[str, str] | None = None, commands=REGISTRY): ...
    last_exit_code: int
    def execute(self, line: str) -> ExecResult   # никогда не бросает ShellError наружу
```

`Shell.execute` ловит `ShellError` и превращает её в `stderr` + `exit_code` (127 для
«command not found», 2 для синтаксиса/аргументов, как в bash). Пустая строка / только
пробелы → пустой результат без ошибки.

## 2. Какими средствами реализуется фича

### GUI (PyQt6)
- `QMainWindow` с центральным `TerminalWidget(QWidget)`:
  - `QPlainTextEdit` (read-only, моноширинный шрифт `QFontDatabase.systemFont(FixedFont)`,
    тёмная палитра через stylesheet) — лента вывода;
  - снизу `QLabel` с приглашением `user@host:~$ ` + `QLineEdit` для ввода.
- После ввода в ленту печатается эхо `user@host:~$ <команда>`, затем вывод команды;
  stderr — красным (через `appendHtml` с экранированием `html.escape`, либо `QTextCharFormat`).
- История команд: список + индекс, стрелки ↑/↓ через переопределение `keyPressEvent`
  у наследника `QLineEdit` (или `eventFilter`).
- Связь виджета и логики — сигнал `command_entered = pyqtSignal(str)`.
- `exit` → `QApplication.exit(code)`, `app.run()` возвращает код в `sys.exit`.
- Фокус всегда на строке ввода; автопрокрутка ленты вниз.

### Заголовок окна
- `getpass.getuser()` (с fallback на `os.environ["USER"]`/`"user"`), `socket.gethostname()`.
- `window_title()` → `f"Эмулятор - [{user}@{host}]"` — в `core/sysinfo.py`, чтобы тестировалось.

### Парсер
Собственный конечный автомат (а не `shlex`), т.к. `shlex` не сообщает, в каких кавычках был
фрагмент, а это нужно для корректного раскрытия переменных. Правила (подмножество POSIX sh):
- разделители — пробельные символы вне кавычек;
- `'...'` — буквально, без раскрытия;
- `"..."` — раскрываются `$VAR` / `${VAR}`, работает `\"`, `\\`, `\$`;
- `\x` вне кавычек — экранирование символа;
- `$NAME` — имя `[A-Za-z_][A-Za-z0-9_]*`; `${NAME}`; неизвестная переменная → пустая строка
  (как в bash); одиночный `$` без имени остаётся литералом `$`;
- `$?` — код возврата предыдущей команды (Shell передаёт его в env-обёртке, опционально);
- `~` в начале слова (вне кавычек) → `$HOME` (опционально, но полезно для `cd ~`);
- незакрытая кавычка или `${` без `}` → `ParseError`;
- слово, полностью ставшее пустым из-за раскрытия несуществующей переменной без кавычек,
  отбрасывается (как в sh); `""` даёт пустой аргумент.

### Команды
- `ls [args...]` — заглушка: печатает `ls` и аргументы, напр. `ls: args=['-l', '/home/arthur']`.
  Проверка аргументов: допустимы опции из набора `-a -l -h` (и их комбинации `-la`);
  неизвестная → `CommandArgsError("ls: invalid option -- 'x'")`.
- `cd [dir]` — заглушка: печатает `cd: args=['/tmp']`. Больше одного аргумента →
  `cd: too many arguments`.
- `exit [n]` — `should_exit=True`, код `n` (по умолчанию `Shell.last_exit_code`, как в bash).
  Нечисловой аргумент → `exit: abc: numeric argument required`; >1 аргумента →
  `exit: too many arguments` (выход не выполняется).
- Неизвестная команда → `repl: foo: command not found`.

### Инструменты / окружение
- Python 3.14, `uv`. Зависимость `PyQt6` (`uv add pyqt6`), dev-зависимость `pytest`
  (`uv add --dev pytest`).
- Исправить `pyproject.toml`: пакет называется `repl`, а проект — `qt-repl`, поэтому
  нужно `[tool.uv.build-backend] module-name = "repl"` и `[project.scripts] repl = "repl:main"`
  (текущий `conf_uprav_1:main` указывает на несуществующий модуль).
- Тесты ядра — `uv run pytest`. Smoke-тест GUI: `QT_QPA_PLATFORM=offscreen` —
  создать `MainWindow`, проверить заголовок, эмулировать ввод и проверить вывод.

## 3. Порядок работы

1. `pyproject.toml`: module-name, entry point, зависимости; `uv sync`.
2. `core/errors.py`, `core/sysinfo.py`.
3. `core/parser.py` + `tests/test_parser.py` (кавычки, `$HOME`, `${HOME}`, неизвестные
   переменные, экранирование, незакрытая кавычка).
4. `core/commands.py` + `tests/test_commands.py`.
5. `core/shell.py` + `tests/test_shell.py` (пустая строка, неизвестная команда, ошибки
   аргументов, exit).
6. `ui/terminal.py`, `ui/main_window.py`, `app.py`, `__init__.py`, `__main__.py`.
7. Smoke-тест GUI в offscreen-режиме (`tests/test_gui_smoke.py`, пропускается, если PyQt6
   не импортируется).
8. README: как запустить (`uv run repl`), пример интерактивной сессии, демонстрирующий все
   функции и ошибки (п.7 требований).
9. Коммит на ветке `feat/repl`:
   `feat(repl): add GUI REPL prototype with env-var parser and stub commands`.

## Пример ожидаемой сессии

```
arthur@host:~$ ls -l $HOME
ls: args=['-l', '/home/arthur']
arthur@host:~$ cd "${HOME}/my dir" '$HOME'
cd: too many arguments
arthur@host:~$ cd '$HOME'
cd: args=['$HOME']
arthur@host:~$ ls -z
ls: invalid option -- 'z'
arthur@host:~$ foo bar
repl: foo: command not found
arthur@host:~$ echo "unterminated
repl: syntax error: unterminated double quote
arthur@host:~$ exit abc
exit: abc: numeric argument required
arthur@host:~$ exit
```

## Вне рамок этапа 1
Аргументы командной строки, стартовые скрипты (этап 2), VFS и реальная логика `ls`/`cd`
(этапы 3–4). Архитектура «ядро без Qt» закладывает для этого основу, но код под будущие
этапы сейчас не пишем.
