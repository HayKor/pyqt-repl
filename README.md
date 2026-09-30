# PyQt GUI REPL w/ VFS

Учебный проект: эмулятор командной оболочки UNIX-подобной ОС с графическим
интерфейсом (PyQt6).

## Архитектура

Ядро оболочки (`src/repl/core/`) не импортирует Qt и не зависит от GUI —
его логика проверяется обычным `pytest` без дисплея:

- `core/parser.py` — токенизатор командной строки (кавычки, `\`, `$VAR`,
  `${VAR}`, `~`, `$?`);
- `core/commands.py` — команды `ls`/`cd` (по-прежнему заглушки; реальная
  логика — следующий этап), `exit`, `vfs-info` и их реестр; `Command.run`
  принимает `CommandContext` (VFS, `cwd`, `$?`, окружение);
- `core/shell.py` — `Shell.execute(line)`, связывает парсер, команды и VFS,
  превращает исключения в текст ошибки и код возврата (как в bash);
- `core/vfs.py` — модель VFS в памяти (`VDir`/`VFile`/`VFS`) и разрешение
  путей (`normalize`/`resolve`);
- `core/vfs_loader.py` — загрузка VFS из XML (`load_vfs`), `describe(vfs)`
  для строки `[vfs] loaded ...`;
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

## Параметры запуска

```
uv run repl [--vfs PATH] [--script PATH]
```

- `--vfs PATH` — путь к образу VFS (XML, см. «Виртуальная файловая
  система» ниже). Загружается в память сразу после открытия окна, до
  запуска стартового скрипта.
- `--script PATH` — путь к стартовому скрипту эмулятора (см. ниже), который
  выполняется сразу после открытия окна (и после загрузки VFS).

Оба параметра разбираются `argparse` **до** создания `QApplication`: неизвестный
флаг, `--script` без значения и т.п. печатают `usage: ...` в stderr и завершают
процесс с кодом `2`, не открывая окно; `--help` печатает справку и код `0`.

При каждом запуске в начале ленты вывода (и в stdout процесса) печатаются
отладочные строки со всеми параметрами:

```
[config] vfs    = <not set>
[config] script = /home/arthur/Projects/conf-uprav-1/scripts/startup/basic.repl (exists)
```

Для незаданного параметра выводится `<not set>`; для заданного — абсолютный
путь и пометка `(exists)` / `(not found)` в зависимости от того, существует ли
файл.

## Стартовый скрипт

Стартовый скрипт (`--script PATH`) — обычный текстовый файл в кодировке UTF-8,
где каждая непустая строка выполняется построчно тем же интерпретатором
команд, что и интерактивный ввод. Поддерживаются комментарии: `#` вне кавычек
в начале слова начинает комментарий до конца строки — как отдельной строкой
(`# comment`), так и после команды (`ls -l # comment`); `#` внутри слова
(`a#b`) или в кавычках (`'#'`, `"#"`) остаётся обычным символом, `\#` — его
литеральное экранирование. Пустые и чисто комментарные строки не выполняются и
не выводятся в ленту.

Каждая исполняемая строка сначала «эхоится» в ленту (`приглашение + строка`),
затем показывается её результат — точно так же, как при ручном вводе. Если
команда завершается с ненулевым кодом возврата, выполнение скрипта
прерывается, печатается сообщение

```
repl: <script>: line <N>: aborted (exit code <code>)
```

красным цветом, и эмулятор возвращается в обычный интерактивный режим —
последующие строки скрипта не выполняются. Если скрипт сам вызывает `exit`,
окно закрывается с указанным кодом возврата, как и при интерактивном вводе
`exit`. Ошибки чтения файла (нет такого файла, каталог вместо файла, нет прав,
содержимое не в UTF-8) также выводятся красным, после чего эмулятор работает
в обычном интерактивном режиме.

## Виртуальная файловая система

VFS полностью живёт в памяти: `--vfs PATH` указывает на XML-файл, который
читается один раз как байты (для SHA-256) и разбирается в дерево каталогов
(`VDir`) и файлов (`VFile`); ни сам образ, ни что-либо производное от него
никогда не записывается на диск. Формат:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<vfs name="demo" mode="755" owner="root" group="root">
  <dir name="home">
    <dir name="user" owner="user" group="user">
      <file name="notes.txt" mode="644">hello
world
</file>
      <file name=".profile">export X=1</file>
      <file name="logo.bin" encoding="base64">iVBORw0KGgo=</file>
    </dir>
  </dir>
  <dir name="tmp" mode="777"/>
</vfs>
```

Правила (любое нарушение → ошибка загрузки с пометкой `invalid format`):
корневой элемент — `<vfs>` (сам каталог `/`); дочерние элементы — только
`<dir>`/`<file>`; `name` обязателен у `<dir>`/`<file>` (непустой, без `/`, не
`.`/`..`, уникален в своём каталоге); `mode` — три восьмеричные цифры
(допускается ведущий `0`), по умолчанию `755` для каталогов и `644` для
файлов; `owner`/`group` по умолчанию `root`; `encoding` у `<file>` — `text`
(по умолчанию, UTF-8 как есть) или `base64` (пробельные символы перед
декодированием удаляются).

При запуске с `--vfs` VFS загружается сразу после отладочных `[config]`-строк
и до стартового скрипта:

```
[vfs] loaded 'demo' (3 dirs, 3 files)
```

Если загрузка не удалась (нет файла, это каталог, невалидный XML или формат
не соответствует схеме), сообщение об ошибке печатается красным, а эмулятор
продолжает работать с пустой VFS (`vfs-info` в этом случае сообщает, что VFS
не загружена). Без `--vfs` ничего из этого не печатается.

Команда `vfs-info` (без аргументов) печатает имя VFS и SHA-256 её XML-файла:

```
arthur@host:~$ vfs-info
name: demo
sha256: 3f5a...e1
```

## Скрипты ОС

`scripts/*.sh` — исполняемые bash-скрипты, вызывающие эмулятор
(`uv run repl ...`) со всеми комбинациями параметров командной строки, включая
ошибочные:

- `run_default.sh` — без параметров;
- `run_vfs.sh` — только `--vfs` (существующий и несуществующий путь);
- `run_script.sh` — только `--script`;
- `run_all_params.sh` — `--vfs` и `--script` вместе;
- `run_script_errors.sh` — стартовый скрипт с ошибкой команды/аргументов и
  несуществующий скрипт;
- `run_bad_args.sh` — ошибки аргументов командной строки (неизвестный флаг,
  `--script` без значения, `--help`);
- `vfs_minimal.sh` — VFS из одного корня (`vfs/minimal.xml`);
- `vfs_multi.sh` — несколько файлов в корне, включая скрытый и base64
  (`vfs/multi.xml`);
- `vfs_deep.sh` — VFS из ≥3 уровней (`vfs/deep.xml`), стартовый скрипт
  прогоняет все команды этапов 1-3;
- `vfs_errors.sh` — ошибки загрузки VFS: отсутствующий файл, каталог вместо
  файла и каждый образ из `vfs/broken/`;
- `stage3_errors.sh` — стартовые скрипты с одной ошибкой в конце
  (неизвестная команда, неверная опция `ls`) и `vfs-info` без `--vfs`.

Соответствующие стартовые скрипты эмулятора лежат в `scripts/startup/*.repl`.
Под офскрин-платформой Qt (`QT_QPA_PLATFORM=offscreen`) запуски, которые не
заканчиваются командой `exit`, не завершаются сами — окно остаётся открытым в
интерактивном режиме, поэтому такой вызов нужно прерывать вручную (например,
`timeout`).

## Тесты

```bash
uv run pytest -q
```

Тесты ядра (`test_parser.py`, `test_commands.py`, `test_shell.py`,
`test_config.py`, `test_script.py`, `test_vfs.py`, `test_vfs_loader.py`)
запускаются без дисплея. GUI smoke-тест (`test_gui_smoke.py`) требует PyQt6
и офскрин-платформу Qt (пропускается автоматически, если PyQt6 не
установлен):

```bash
QT_QPA_PLATFORM=offscreen uv run pytest -q
```

## Структура проекта

```
src/repl/
├── __init__.py         # main(): parse_args() → sys.exit(app.run(cfg))
├── __main__.py         # python -m repl
├── app.py              # печать debug-строк, QApplication, MainWindow, exec()
├── core/                # чистый Python, без Qt
│   ├── errors.py
│   ├── sysinfo.py
│   ├── parser.py        # + комментарии `#`
│   ├── commands.py      # Command.run(args, ctx); ls/cd (заглушки), exit, vfs-info
│   ├── shell.py         # Shell(vfs=...), CommandContext, cwd
│   ├── config.py        # AppConfig, parse_args, format_config
│   ├── script.py        # load_script, iter_script, abort_message
│   ├── vfs.py           # VNode/VDir/VFile/VFS, normalize/resolve
│   └── vfs_loader.py    # load_vfs, describe
└── ui/
    ├── main_window.py   # config, debug-вывод, загрузка VFS, запуск стартового скрипта
    └── terminal.py       # echo_command()
scripts/
├── run_default.sh
├── run_vfs.sh
├── run_script.sh
├── run_all_params.sh
├── run_script_errors.sh
├── run_bad_args.sh
├── vfs_minimal.sh
├── vfs_multi.sh
├── vfs_deep.sh
├── vfs_errors.sh
├── stage3_errors.sh
└── startup/
    ├── basic.repl
    ├── with_error.repl
    ├── bad_args.repl
    ├── exit.repl
    ├── vfs_info.repl
    ├── stage3.repl
    ├── stage3_err_unknown.repl
    └── stage3_err_ls.repl
vfs/
├── minimal.xml
├── multi.xml
├── deep.xml
└── broken/
    ├── not_xml.xml
    ├── wrong_root.xml
    ├── bad_base64.xml
    ├── duplicate.xml
    └── bad_mode.xml
tests/
├── test_parser.py
├── test_commands.py
├── test_shell.py
├── test_config.py
├── test_script.py
├── test_vfs.py
├── test_vfs_loader.py
└── test_gui_smoke.py
```

