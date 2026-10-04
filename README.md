# PyQt GUI REPL w/ VFS

Учебный проект: эмулятор командной оболочки UNIX-подобной ОС с графическим
интерфейсом (PyQt6). Окно ведёт себя как терминал: приглашение
`user@host:<cwd>$`, ввод команд с историей (стрелки вверх/вниз), вывод и
ошибки в общей ленте. Файловая система виртуальная: загружается из XML-образа
и живёт только в памяти, поэтому реальные файлы эмулятор не трогает.

Описание функций и настроек:

- [Параметры запуска](#параметры-запуска): `--vfs`, `--script`;
- [Стартовый скрипт](#стартовый-скрипт): формат и поведение при ошибках;
- [Виртуальная файловая система](#виртуальная-файловая-система): формат XML
  и `vfs-info`;
- [Команды](#команды): `ls`, `cd`, `cat`, `tac`, `chmod`, `chown`, `exit`,
  `vfs-info`;
- [Скрипты ОС](#скрипты-ос): готовые сценарии запуска.

## Архитектура

Ядро оболочки (`src/repl/core/`) не импортирует Qt и не зависит от GUI —
его логика проверяется обычным `pytest` без дисплея:

- `core/parser.py` — токенизатор командной строки (кавычки, `\`, `$VAR`,
  `${VAR}`, `~`, `$?`);
- `core/commands.py` — команды `ls`/`cd` (реальная логика поверх VFS),
  `cat`/`tac`, `chmod`/`chown`, `exit`, `vfs-info` и их реестр; `Command.run`
  принимает `CommandContext` (VFS, `cwd`, `oldpwd`, `$?`, окружение);
- `core/modes.py` — разбор MODE для `chmod` (`parse_mode`): восьмеричный и
  символьный синтаксис;
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

## Сборка и запуск

Требуется Python 3.14 и [`uv`](https://docs.astral.sh/uv/). Основные действия
доступны через `Makefile`:

| Команда | Что делает |
|---------|------------|
| `make install` | `uv sync`: создаёт `.venv` и ставит зависимости |
| `make run ARGS="..."` | запускает эмулятор через `./run.sh` |
| `make test` | `QT_QPA_PLATFORM=offscreen uv run pytest -q` |
| `make lint` | `uv run ruff check`: стиль, docstrings, сложность |
| `make build` | `uv build`: собирает wheel и sdist в `dist/` |
| `make clean` | удаляет `dist/`, кеши и `__pycache__` |

Без `make`:

```bash
uv sync
./run.sh            # то же, что uv run repl
uv run python -m repl
uv build
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
arthur@host:/$ vfs-info
name: demo
sha256: 3f5a...e1
```

## Команды

Приглашение — `user@host:<cwd>$ ` (`/` для корня VFS); `MainWindow` обновляет
его после каждой команды (и интерактивной, и из стартового скрипта), так что
эхо следующей строки уже показывает актуальный `cwd`.

Опции разбираются как на этапе 1: `-la` эквивалентно `-l -a`, `--` не
поддерживается; неизвестная опция → `<cmd>: invalid option -- 'x'` (код 2).
Ошибки по отдельным путям/файлам не прерывают обработку остальных аргументов:
сообщения копятся в `stderr`, итоговый код ненулевой, если была хоть одна
ошибка. Вывод команд никогда не заканчивается переводом строки — его
добавляет сам виджет терминала.

### `ls [-a] [-l] [-h] [PATH...]`

Работает поверх `ctx.vfs`/`ctx.cwd` (`VFS.resolve`/`normalize`). Без путей —
листинг `ctx.cwd`. Скрытые (`.`-начинающиеся) элементы показываются только с
`-a` (вместе с `.`/`..`). Короткий формат — имена через два пробела в одну
строку, без колонок и без суффиксов у каталогов. `-l` — по строке на
элемент (`drwxr-xr-x user user  4096 name`; владелец/группа/размер
выровнены по ширине), перед листингом каталога — строка `total N` (N — число
показанных элементов, упрощение: реальных блоков диска в модели VFS нет).
Дат нет — в модели VFS нет времени модификации. `-h` (только вместе с `-l`,
иначе игнорируется) выводит размеры в духе GNU: `1.5K`, `12M` (одна цифра
после точки при значении < 10, округление вверх). Путь-файл выводит сам
файл; несколько путей — сначала файлы, затем каталоги с заголовками `path:`
и пустой строкой между блоками (как GNU `ls`). Ошибка по пути —
`ls: cannot access 'x': No such file or directory`/`Not a directory`, код 2.

### `cd [DIR]`

Без аргумента — переход в корень VFS `/` (в модели VFS обычно нет ветки,
совпадающей с реальным `$HOME`, так что `cd` без аргументов и `cd ~` — это,
как правило, разные вещи: `~` раскрывается парсером в реальный `$HOME`, что
почти всегда ведёт к ошибке «No such file or directory» — это ожидаемо).
`cd -` — переход в предыдущий каталог (`OLDPWD`, хранится в `Shell`/
`CommandContext`) с печатью нового пути, как в bash; если предыдущего
каталога ещё нет — `cd: OLDPWD not set` (код 1). Прочие ошибки:
`cd: x: No such file or directory`, `cd: x: Not a directory` (код 1),
`cd: too many arguments` (код 2). Права доступа при переходе не проверяются
(это будет в следующем этапе) — только отображаются через `ls -l`.

### `cat [-n] FILE...`

Конкатенация содержимого файлов; байты декодируются как UTF-8 с
`errors="replace"`. `-n` — сквозная нумерация строк через все файлы, формат
GNU `%6d\t%s`. Без аргументов — `cat: missing file operand` (у эмулятора нет
стандартного ввода, код 2). Каталог в аргументах → `cat: x: Is a directory`;
отсутствующий файл → `cat: x: No such file or directory`; код 1, но
остальные файлы всё равно выводятся.

### `tac FILE...`

Построчный вывод в обратном порядке, отдельно для каждого файла (результаты
идут в порядке аргументов, файлы между собой не перемешиваются). Повторяет
поведение GNU `tac` при отсутствии завершающего `\n` у последней строки:
`printf 'a\nb' | tac` → `ba`. Опций нет — любой флаг → invalid option; без
файлов — `tac: missing file operand`; ошибки по файлам — как у `cat`.

### `chmod [-R] MODE FILE...`

Меняет `mode` узла VFS **только в памяти** (XML-источник не трогается,
`vfs-info` продолжает показывать его исходный SHA-256). `MODE` — восьмеричный
(`^0?[0-7]{3}$`, например `755`/`0644`; заменяет права целиком, спецбиты
setuid/setgid/sticky не поддерживаются — `4755` это invalid mode) или
символьный: список через запятую из клаузул `[ugoa]*([-+=][rwx]*)+`
(`u+x`, `go-w`, `a=r`, `+x`, `u=rwx,g=rx,o=`, `u+x-w`); пустое «кто» значит
`a`; umask не применяется (в эмуляторе его нет); `=` с пустым списком прав
сбрасывает права роли. `X`, `s`, `t` и копирование другой роли (`u=g`) не
поддерживаются → invalid mode. `-R` — рекурсивно (сам каталог и все
потомки, применяет `MODE` заново к текущим правам каждого узла, а не
копирует получившееся значение). Аргумент вида `-x`/`-w` трактуется как
`MODE`, если подходит под символьный синтаксис (как GNU `chmod -x file`),
иначе — как неизвестная опция. Ошибки: `chmod: missing operand` (нет
аргументов) / `chmod: missing operand after 'MODE'` (нет файлов) — код 2;
`chmod: invalid mode: 'x'` — код 1; `chmod: cannot access 'x': No such file
or directory`/`Not a directory` — код 1, остальные файлы обрабатываются;
`chmod: invalid option -- 'x'` — код 2. Вывода при успехе нет.

### `chown [-R] OWNER[:GROUP] FILE...`

Меняет `owner`/`group` узла VFS, тоже только в памяти. Формы: `user` (меняет
владельца, группа остаётся прежней), `user:group` (оба), `user:` (владелец
меняется, группа остаётся прежней — упрощение: в GNU это «группа входа
пользователя», здесь её просто нет), `:group` (меняется только группа).
Имена — `^[a-z_][a-z0-9_-]*$` или число (uid/gid хранится как строка);
пустая спецификация, одиночное `:` или неверное имя →
`chown: invalid user: 'x'` / `chown: invalid group: 'x'`, код 1. Проверки
прав нет — эмулятор всегда работает как суперпользователь. `-R` — как у
`chmod`. Ошибки операндов/путей — как у `chmod` (`chown: missing operand`,
`chown: cannot access ...`). Вывода при успехе нет.

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
  прогоняет все команды этапов 1-3 (запускается с `HOME=/home/user`, чтобы
  `$HOME` попадал в дерево VFS);
- `vfs_errors.sh` — ошибки загрузки VFS: отсутствующий файл, каталог вместо
  файла и каждый образ из `vfs/broken/`;
- `stage3_errors.sh` — стартовые скрипты с одной ошибкой в конце
  (неизвестная команда, неверная опция `ls`) и `vfs-info` без `--vfs`;
- `stage4.sh` — `stage4.repl` (все режимы `ls`/`cd`/`cat`/`tac` на
  `vfs/deep.xml`, `HOME=/home/user`) и по одному `stage4_err_*.repl` на
  каждую ошибку (`ls` без пути/с неверной опцией, `cd` в файл/по
  несуществующему пути, `cat` каталога/несуществующего файла, `tac` без
  аргументов);
- `stage5.sh` — `stage5.repl` (все режимы `chmod`/`chown` на
  `vfs/deep.xml`: восьмеричный и символьный `MODE` (включая списки через
  запятую, `=` и `-x` как `MODE`), `-R`, все формы `OWNER[:GROUP]`,
  `vfs-info` до и после — хеш не меняется) и по одному `stage5_err_*.repl`
  на каждую ошибку (`chmod` — invalid mode, missing operand, cannot
  access, invalid option; `chown` — invalid user, invalid group).

Запуск с переопределённым `$HOME` устроен как `uv run env HOME=... repl ...`
(а не `HOME=... uv run repl ...`), потому что сам `uv` использует `$HOME` для
своего кеша — переопределять его для процесса `uv` целиком нельзя, только для
запускаемого им `repl`.

Соответствующие стартовые скрипты эмулятора лежат в `scripts/startup/*.repl`.
Под офскрин-платформой Qt (`QT_QPA_PLATFORM=offscreen`) запуски, которые не
заканчиваются командой `exit`, не завершаются сами — окно остаётся открытым в
интерактивном режиме, поэтому такой вызов нужно прерывать вручную (например,
`timeout`).

## Тесты и проверка стиля

```bash
uv run pytest -q
uv run ruff check
```

`tests/conftest.py` включает офскрин-платформу Qt
(`QT_QPA_PLATFORM=offscreen`), так что отдельный дисплей не нужен.

Тесты ядра (`test_parser.py`, `test_commands.py`, `test_modes.py`,
`test_shell.py`, `test_config.py`, `test_script.py`, `test_vfs.py`,
`test_vfs_loader.py`) запускаются без дисплея. GUI smoke-тест
(`test_gui_smoke.py`) требует PyQt6 и офскрин-платформу Qt (пропускается
автоматически, если PyQt6 не установлен).

Настройки `ruff` лежат в `pyproject.toml`: строки до 80 символов,
цикломатическая сложность ≤ 10, не больше 7 аргументов у функции, docstrings
у модулей, классов и публичных функций, без «магических» чисел в сравнениях,
имена по PEP 8.

## Примеры использования

```bash
./run.sh                                     # пустая VFS, интерактивный режим
./run.sh --vfs vfs/deep.xml                  # загрузить VFS из XML
./run.sh --vfs vfs/deep.xml --script scripts/startup/stage4.repl
make run ARGS="--vfs vfs/multi.xml"
./run.sh --help
```

Пример сеанса на `vfs/deep.xml` (с `HOME=/home/user`):

```
[vfs] loaded 'deep' (11 dirs, 7 files)
user@host:/$ ls
etc  home  tmp  usr  var
user@host:/$ cd ~/docs
user@host:/home/user/docs$ ls -l
total 2
-rw-r--r-- user user   0 empty.txt
-rw-r--r-- user user  64 notes.txt
user@host:/home/user/docs$ cat -n notes.txt
     1	First line of notes.
     2	Second line of notes.
     3	Third and last line.
user@host:/home/user/docs$ chmod u+x,go-r notes.txt
user@host:/home/user/docs$ ls -l notes.txt
-rwx------ user user  64 notes.txt
user@host:/home/user/docs$ cd /nope
cd: /nope: No such file or directory
```

Больше сценариев (включая ошибочные) — в `scripts/*.sh` и
`scripts/startup/*.repl`, см. «Скрипты ОС».

## Структура проекта

```
run.sh                  # запуск эмулятора: uv run repl "$@"
Makefile                # install / run / test / lint / build / clean
pyproject.toml          # зависимости, точка входа repl, настройки ruff
docs/plans/             # планы этапов
src/repl/
├── __init__.py         # main(): parse_args() → sys.exit(app.run(cfg))
├── __main__.py         # python -m repl
├── app.py              # печать debug-строк, QApplication, MainWindow, exec()
├── core/                # чистый Python, без Qt
│   ├── errors.py
│   ├── sysinfo.py
│   ├── parser.py        # + комментарии `#`
│   ├── commands.py      # Command.run(args, ctx); ls/cd/cat/tac/chmod/chown, exit, vfs-info
│   ├── modes.py         # parse_mode(spec, current_mode); ModeError
│   ├── shell.py         # Shell(vfs=...), CommandContext, cwd/oldpwd
│   ├── config.py        # AppConfig, parse_args, format_config
│   ├── script.py        # load_script, iter_script, abort_message
│   ├── vfs.py           # VNode/VDir/VFile/VFS, normalize/resolve
│   └── vfs_loader.py    # load_vfs, describe
└── ui/
    ├── main_window.py   # config, debug-вывод, загрузка VFS, запуск стартового скрипта,
    │                    # приглашение с cwd
    └── terminal.py       # echo_command(), set_prompt()
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
├── stage4.sh
├── stage5.sh
└── startup/
    ├── basic.repl
    ├── with_error.repl
    ├── bad_args.repl
    ├── exit.repl
    ├── vfs_info.repl
    ├── stage3.repl
    ├── stage3_err_unknown.repl
    ├── stage3_err_ls.repl
    ├── stage4.repl
    ├── stage4_err_ls_missing_path.repl
    ├── stage4_err_ls_bad_option.repl
    ├── stage4_err_cd_into_file.repl
    ├── stage4_err_cd_missing_path.repl
    ├── stage4_err_cat_directory.repl
    ├── stage4_err_cat_missing_file.repl
    ├── stage4_err_tac_missing_operand.repl
    ├── stage5.repl
    ├── stage5_err_chmod_invalid_mode.repl
    ├── stage5_err_chmod_missing_operand.repl
    ├── stage5_err_chmod_missing_file.repl
    ├── stage5_err_chown_invalid_user.repl
    ├── stage5_err_chown_invalid_group.repl
    └── stage5_err_chmod_invalid_option.repl
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
├── conftest.py
├── test_parser.py
├── test_commands.py
├── test_modes.py
├── test_shell.py
├── test_config.py
├── test_script.py
├── test_vfs.py
├── test_vfs_loader.py
└── test_gui_smoke.py
```

