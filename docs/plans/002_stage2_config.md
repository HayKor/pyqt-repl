# План 002 — Этап 2: Конфигурация (вариант №4)

## Цель

Сделать эмулятор настраиваемым: параметры командной строки (путь к VFS, путь к
стартовому скрипту), выполнение стартового скрипта с отображением диалога,
отладочный вывод всех параметров при запуске, сообщения об ошибках скрипта,
набор скриптов ОС для проверки всех параметров.

## Требования этапа (из docs/task.pdf) → как закрываем

| # | Требование | Реализация |
|---|------------|------------|
| — | Отладочный вывод всех параметров при запуске | `format_config(cfg)` → строки `[config] ...`; печать в stdout процесса **и** первыми строками в окне терминала |
| 1 | Параметры CLI: путь к VFS, путь к стартовому скрипту | `argparse` в `core/config.py`: `--vfs PATH`, `--script PATH` → `AppConfig` |
| 2 | Стартовый скрипт с комментариями (синтаксис языка реализации — Python, `#`); виден ввод и вывод | `#` вне кавычек в начале слова — комментарий до конца строки (в парсере, как в Python/sh); `core/script.py` построчно выполняет скрипт через тот же `Shell`, GUI печатает `prompt + строка` и результат |
| 3 | Ошибка во время исполнения скрипта | Скрипт прерывается на первой команде с ненулевым кодом; сообщение `repl: <script>: line N: ...`; ошибки чтения файла (нет файла, каталог, не UTF-8) тоже сообщаются; после этого — обычный интерактивный режим |
| 4 | Несколько скриптов ОС, вызывающих эмулятор со всеми параметрами | `scripts/*.sh` (bash) + стартовые скрипты эмулятора `scripts/startup/*.repl` |
| 5 | Коммит | Conventional Commits: `feat(config): ...` на ветке `feat/config` |

## 1. Какими средствами реализуется фича

- **`argparse`** (stdlib) — разбор параметров. Разбираем `sys.argv[1:]` строго
  (`parse_args`, не `parse_known_args`) **до** создания `QApplication`; в
  `QApplication` передаём только `[sys.argv[0]]`. Ошибка аргументов → стандартное
  `usage: ...` в stderr и код 2 без запуска GUI (как у обычных CLI-утилит).
  Qt-платформу по-прежнему можно задать через `QT_QPA_PLATFORM`.
- **`pathlib.Path`** — пути; в `AppConfig` храним как передано, в отладочный вывод
  пишем и абсолютный путь (`Path.resolve()`) + признак существования.
- **`dataclasses`** — неизменяемый `AppConfig`.
- **Существующий `Shell` + парсер** — стартовый скрипт выполняется построчно тем же
  `Shell.execute`, что и интерактивный ввод: один код для обоих режимов.
- **`QTimer.singleShot(0, ...)`** (PyQt6) — запуск скрипта после показа окна, чтобы
  пользователь видел окно с диалогом, а не пустой старт.
- **bash** — скрипты реальной ОС в `scripts/` (запуск через `uv run repl ...`).
- **pytest** + `QT_QPA_PLATFORM=offscreen` — тесты ядра и GUI smoke.

VFS на этом этапе **не загружается** (это этап 3): путь только принимается,
хранится в `AppConfig` и печатается в отладочном выводе (с пометкой, существует ли
файл). Проверка формата — на этапе 3.

## 2. Архитектура / изменения в файлах

Ядро по-прежнему без Qt.

```
src/repl/
├── __init__.py        # main(): cfg = parse_args(sys.argv[1:]); sys.exit(app.run(cfg))
├── app.py             # run(config): печать debug в stdout, QApplication([argv0]), MainWindow(config=...)
├── core/
│   ├── config.py      # НОВЫЙ: AppConfig, build_arg_parser(), parse_args(argv), format_config(cfg)
│   ├── script.py      # НОВЫЙ: ScriptError, load_script(path), iter_script(shell, lines)
│   ├── errors.py      # + ScriptError(ShellError)
│   └── parser.py      # + комментарии `#`
└── ui/
    └── main_window.py # принимает config; печатает debug-строки; запускает скрипт
scripts/
├── run_default.sh           # без параметров
├── run_vfs.sh               # только --vfs (существующий и несуществующий путь)
├── run_script.sh            # только --script (startup/basic.repl)
├── run_all_params.sh        # --vfs + --script
├── run_script_errors.sh     # скрипт с ошибкой; несуществующий скрипт
├── run_bad_args.sh          # неизвестный флаг, --script без значения, --help
└── startup/
    ├── basic.repl           # комментарии (строчные и в конце строки), ls/cd с $HOME, кавычки
    ├── with_error.repl      # корректные команды → неизвестная команда → команды после (не выполняются)
    ├── bad_args.repl        # ошибка аргументов (ls -z) посреди скрипта
    └── exit.repl            # несколько команд и `exit 3` — эмулятор закрывается с кодом 3
tests/
├── test_config.py     # НОВЫЙ
├── test_script.py     # НОВЫЙ
├── test_parser.py     # + комментарии
└── test_gui_smoke.py  # + debug-вывод, запуск скрипта, ошибка скрипта
```

### Ключевые интерфейсы

```python
# core/config.py
@dataclass(frozen=True)
class AppConfig:
    vfs_path: Path | None = None
    script_path: Path | None = None

def build_arg_parser() -> argparse.ArgumentParser   # prog="repl"
def parse_args(argv: Sequence[str] | None = None) -> AppConfig
def format_config(cfg: AppConfig) -> list[str]
# Пример:
#   [config] vfs    = /abs/path/fs.xml (exists)
#   [config] script = /abs/scripts/startup/basic.repl (exists)
# Для незаданного: "[config] vfs    = <not set>"; несуществующий: "(not found)".

# core/errors.py
class ScriptError(ShellError): ...   # "repl: scripts/x.repl: No such file or directory"

# core/script.py
@dataclass
class ScriptStep:
    lineno: int
    line: str           # исходная строка (без \n) — для эха в терминале
    result: ExecResult

def load_script(path: Path) -> list[str]
    # читает UTF-8; FileNotFoundError / IsADirectoryError / PermissionError /
    # UnicodeDecodeError → ScriptError с bash-подобным текстом

def is_blank_or_comment(line: str) -> bool   # пустая или только комментарий

def iter_script(shell: Shell, lines: list[str]) -> Iterator[ScriptStep]
    # пропускает пустые и чисто комментарные строки (не эхоит их);
    # выполняет остальные через shell.execute; yield ScriptStep;
    # останавливается после шага с exit_code != 0 или should_exit=True
```

Сообщение об ошибке исполнения формирует вызывающий (GUI) по последнему шагу:
`repl: <script_path>: line <N>: aborted (exit code <code>)` — печатается красным после
stderr самой команды. Удобно вынести в `core/script.py` функцию
`abort_message(path, step) -> str`, чтобы её проверял pytest.

### Комментарии в парсере

`#` **вне кавычек в начале слова** начинает комментарий до конца строки
(`ls -l # comment`, `# whole line`). `#` внутри слова (`a#b`) или в кавычках (`'#'`,
`"#"`) — обычный символ. Работает и в интерактивном режиме (как в bash/Python).
`\#` — литерал. Строка из одного комментария → пустой argv → no-op.

### Поток запуска

```
main() → parse_args(argv)            # ошибка → usage + exit 2, GUI не создаётся
       → app.run(cfg)
            print(*format_config(cfg), sep="\n")     # отладочный вывод в консоль
            QApplication([argv0]); MainWindow(config=cfg); show()
            MainWindow.__init__: terminal.append_output(debug-строки)
            QTimer.singleShot(0, self._run_startup_script)  если script_path задан
       → app.exec()
```

`MainWindow._run_startup_script()`:
1. `load_script` → при `ScriptError` печатает ошибку красным и возвращается к
   интерактивному режиму.
2. Для каждого `ScriptStep`: `terminal.echo(prompt + step.line)` (новый публичный метод
   `TerminalWidget.echo_command(line)` — выделить из `_on_return_pressed`, чтобы эхо
   было одинаковым), затем stdout/stderr через общий `_show_result(result)` (выделить из
   `_on_command`).
3. Если последний шаг `should_exit` → закрыть приложение с его кодом (как `exit` в sh
   скрипте). Если `exit_code != 0` → печатается `abort_message`. Иначе ничего.
4. Строка ввода остаётся доступной после скрипта.

Для тестов `MainWindow` должен позволять запустить скрипт синхронно: публичный метод
`run_startup_script()`; `QTimer` только вызывает его.

## 3. Порядок работы

1. `core/parser.py`: комментарии `#` + тесты в `tests/test_parser.py`
   (`ls # c`, `# only`, `a#b`, `'#'`, `"#"`, `\#`).
2. `core/errors.py`: `ScriptError`.
3. `core/config.py` + `tests/test_config.py`: без аргументов, `--vfs`, `--script`,
   оба, `--vfs=path`, неизвестный флаг → `SystemExit(2)`, `format_config` для
   заданных/незаданных/несуществующих путей (`tmp_path`).
4. `core/script.py` + `tests/test_script.py`: пропуск комментариев/пустых строк,
   номера строк, остановка на ошибке (команды после не выполняются), остановка на
   `exit`, `$?` между строками скрипта, `load_script` для отсутствующего файла,
   каталога, не-UTF-8.
5. `ui/terminal.py` (`echo_command`), `ui/main_window.py` (config, debug-вывод, скрипт),
   `app.py`, `__init__.py`.
6. `tests/test_gui_smoke.py`: debug-строки видны в окне; скрипт из `tmp_path`
   выполняется с эхом и выводом; ошибка в скрипте даёт `aborted` и команды после неё
   не выполняются; несуществующий скрипт → сообщение; `exit` в скрипте закрывает окно.
   Существующие тесты не ломать (`MainWindow()` без config должен работать).
7. `scripts/*.sh` (исполняемые, `#!/usr/bin/env bash`, `set -u`, `cd` в корень
   репозитория через `$(dirname "$0")/..`, каждый вызов предваряется `echo "== ..."`) и
   `scripts/startup/*.repl`. Проверить каждый вручную:
   `QT_QPA_PLATFORM=offscreen timeout 5 bash scripts/<x>.sh` — debug-вывод есть в
   stdout, ошибки аргументов дают код 2. (Скрипты, не заканчивающиеся `exit`, в
   offscreen будут висеть до `timeout` — это ожидаемо.)
8. README: раздел «Параметры запуска» (`--vfs`, `--script`, пример debug-вывода),
   «Стартовый скрипт» (формат, комментарии, поведение при ошибке), «Скрипты ОС»;
   обновить дерево проекта.
9. `uv run pytest -q` и `QT_QPA_PLATFORM=offscreen uv run pytest -q` — зелёные.
10. Коммит на `feat/config`:
    `feat(config): add CLI options, startup script and debug config output`
    — тело из двух коротких предложений, **без** трейлера `Co-Authored-By: Claude`.

## Пример ожидаемой сессии (`--script scripts/startup/with_error.repl`)

```
[config] vfs    = <not set>
[config] script = /home/arthur/Projects/conf-uprav-1/scripts/startup/with_error.repl (exists)
arthur@host:~$ ls -l $HOME
ls: args=['-l', '/home/arthur']
arthur@host:~$ cd /tmp   # inline comment
cd: args=['/tmp']
arthur@host:~$ foo bar
repl: foo: command not found
repl: scripts/startup/with_error.repl: line 7: aborted (exit code 127)
arthur@host:~$ ▌   ← дальше интерактивный режим
```

## Вне рамок этапа 2

Загрузка и разбор VFS, `vfs-info` (этап 3), реальная логика `ls`/`cd` (этап 4).
