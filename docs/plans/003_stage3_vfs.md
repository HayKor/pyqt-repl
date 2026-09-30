# План 003 — Этап 3: VFS (вариант №4)

## Цель

Подключить виртуальную файловую систему (VFS): загрузка из XML-файла, указанного
параметром `--vfs`, целиком в память; сообщения об ошибках загрузки; служебная команда
`vfs-info`. Реальная логика `ls`/`cd` — на этапе 4; здесь закладываем модель VFS и
разрешение путей, которые понадобятся этапам 4–5.

## Требования этапа (из docs/task.pdf) → как закрываем

| # | Требование | Реализация |
|---|------------|------------|
| 1 | Все операции в памяти, данные VFS не распаковываются и не модифицируются на диске | XML читается один раз как `bytes`, разбирается `xml.etree.ElementTree.fromstring` в дерево `VDir`/`VFile` в памяти. Ни один модуль не пишет на диск |
| 2 | Источник — XML; двоичные данные — base64 | `<file encoding="base64">`; декодирование `base64.b64decode(..., validate=True)` |
| 3 | Ошибка загрузки VFS (нет файла, неверный формат) | `VFSLoadError` с bash-подобным текстом; печатается красным в окне при старте, эмулятор продолжает работу с пустой VFS |
| 4 | `vfs-info`: имя VFS и SHA-256 её данных | `hashlib.sha256(raw_bytes).hexdigest()` от байтов XML-файла; имя — атрибут `name` корня |
| 5 | Скрипты ОС для разных VFS (минимальная, несколько файлов, ≥3 уровня) | `vfs/*.xml` + `scripts/vfs_*.sh` |
| 6 | Стартовый скрипт, тестирующий все команды этапов 1–3, включая VFS и ошибки | `scripts/startup/stage3.repl` + скрипты ошибок (см. ниже: скрипт прерывается на первой ошибке — поведение этапа 2 сохраняем) |
| 7 | Коммит | `feat(vfs): ...` на ветке `feat/vfs` |

## 1. Средства

- **`xml.etree.ElementTree`** (stdlib) — разбор XML. Внешние сущности stdlib не
  раскрывает; для учебного проекта `defusedxml` не нужен.
- **`base64`**, **`hashlib`** (stdlib) — двоичные данные и SHA-256.
- **`dataclasses`** — узлы VFS.
- Разрешение путей — собственная функция по компонентам (`.`/`..`/абсолютные/
  относительные), **не** `os.path`/`pathlib` (они работают с реальной ФС/ОС).

## 2. Формат XML

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

Правила (строгие, любое нарушение → `VFSLoadError` «invalid format»):
- корневой элемент — `<vfs>`; он же каталог `/`. Атрибут `name` необязателен
  (по умолчанию — имя XML-файла без расширения);
- дочерние элементы — только `<dir>` и `<file>`; у `<vfs>`/`<dir>` не должно быть
  непробельного текста; у `<file>` не должно быть дочерних элементов;
- `name` обязателен для `<dir>`/`<file>`: непустой, без `/`, не `.` и не `..`;
  имена в одном каталоге уникальны;
- `mode` — 3 восьмеричные цифры (допускается ведущий `0`: `0644`), по умолчанию
  `755` для каталогов, `644` для файлов; хранится как `int`;
- `owner`/`group` — по умолчанию `root`;
- `encoding` у `<file>`: `text` (по умолчанию; содержимое — текст элемента как есть,
  UTF-8) или `base64` (пробельные символы удаляются перед декодированием; ошибка
  декодирования → invalid format);
- неизвестные элементы/атрибуты → invalid format.

## 3. Архитектура

```
src/repl/core/
├── vfs.py         # НОВЫЙ: VNode/VDir/VFile, VFS (name, sha256, root, loaded), resolve/normalize
├── vfs_loader.py  # НОВЫЙ: load_vfs(path) -> VFS; VFSLoadError
├── errors.py      # + VFSLoadError(ShellError), VFSPathError(ShellError)
├── commands.py    # Command.run(args, ctx); + VfsInfoCommand; ls/cd остаются заглушками
└── shell.py       # Shell хранит vfs и cwd; CommandContext
```

### Ключевые интерфейсы

```python
# core/vfs.py
@dataclass
class VNode:
    name: str
    mode: int
    owner: str
    group: str

@dataclass
class VFile(VNode):
    data: bytes = b""
    @property
    def size(self) -> int: ...

@dataclass
class VDir(VNode):
    children: dict[str, VNode] = field(default_factory=dict)

@dataclass
class VFS:
    name: str
    sha256: str
    root: VDir
    source: Path | None = None        # None → пустая VFS «по умолчанию»
    @property
    def loaded(self) -> bool: ...      # source is not None
    @classmethod
    def empty(cls) -> VFS: ...         # только "/", name="<none>"

    def normalize(self, path: str, cwd: str = "/") -> str
        # абсолютный канонический путь: "/a/b"; ".." у корня остаётся "/"
    def resolve(self, path: str, cwd: str = "/") -> VNode
        # VFSPathError(path, "No such file or directory" | "Not a directory")
        # промежуточный компонент-файл → Not a directory; "file/" → Not a directory

# core/vfs_loader.py
def load_vfs(path: Path) -> VFS
# VFSLoadError сообщения:
#   "repl: vfs: <path>: No such file or directory"
#   "repl: vfs: <path>: Is a directory" / "Permission denied"
#   "repl: vfs: <path>: invalid XML: <msg ExpatError/ParseError>"
#   "repl: vfs: <path>: invalid format: <деталь, напр. 'duplicate name \"a\" in /home'>"

# core/errors.py
class VFSLoadError(ShellError): ...
class VFSPathError(ShellError):
    def __init__(self, path: str, reason: str): ...   # str = f"{path}: {reason}"

# core/commands.py
@dataclass
class CommandContext:
    vfs: VFS
    cwd: str               # абсолютный путь в VFS, меняется командой cd (этап 4)
    last_exit_code: int
    env: Mapping[str, str]

@dataclass
class CommandResult:
    output: str = ""
    error: str = ""        # НОВОЕ: stderr при частичном успехе (нужно этапу 4)
    exit_code: int = 0
    should_exit: bool = False

class Command(ABC):
    def run(self, args: list[str], ctx: CommandContext) -> CommandResult: ...

class VfsInfoCommand(Command):   # name = "vfs-info"
    # без аргументов: "name: demo\nsha256: <hex>"
    # аргументы → CommandArgsError("vfs-info: too many arguments")
    # VFS не загружена → CommandResult(error="vfs-info: no VFS loaded", exit_code=1)

# core/shell.py
class Shell:
    def __init__(self, env=None, commands=REGISTRY, vfs: VFS | None = None): ...
    vfs: VFS           # VFS.empty() по умолчанию
    cwd: str           # "/"
    # execute собирает CommandContext, после run берёт ctx.cwd обратно в self.cwd;
    # result.error → ExecResult.stderr
```

`ExitCommand` берёт код из `ctx.last_exit_code`. Существующие тесты команд
переписать под `ctx` (фикстура/хелпер `make_ctx()`); поведение `ls`/`cd`/`exit` не
меняется.

### Загрузка при старте

`MainWindow.__init__` после `[config]`-строк: если `config.vfs_path` задан —
`load_vfs` → `shell.vfs = vfs` и строка `[vfs] loaded 'demo' (3 dirs, 5 files)`; при
`VFSLoadError` — сообщение красным, остаётся `VFS.empty()`. Без `--vfs` — ничего не
печатается (`[config] vfs = <not set>` уже есть). Загрузка до запуска стартового
скрипта. Обновить `help` у `--vfs` (убрать «not loaded until stage 3»). Логику
«загрузить и вернуть строку-сообщение» держать в core (например,
`vfs_loader.describe(vfs)`), чтобы проверялась pytest'ом.

## 4. Данные для демонстрации

```
vfs/
├── minimal.xml        # <vfs name="minimal"/> — только корень
├── multi.xml          # несколько файлов в корне: текстовые, .hidden, один base64
├── deep.xml           # ≥3 уровня: /home/user/docs/notes.txt, /etc/app/conf.d/x.conf,
│                      # /var/log/app.log, /usr/bin/tool (base64), разные mode/owner, скрытые файлы
└── broken/
    ├── not_xml.xml        # мусор / незакрытый тег → invalid XML
    ├── wrong_root.xml     # <fs> вместо <vfs>
    ├── bad_base64.xml
    ├── duplicate.xml      # два "a" в одном каталоге
    └── bad_mode.xml       # mode="999"
```

`deep.xml` будет основной VFS для этапов 4–5 — сделать его содержательным (многострочные
текстовые файлы для `cat`/`tac`, файл без завершающего `\n`, пустой файл).

Скрипты ОС (bash, как на этапе 2: `#!/usr/bin/env bash`, `set -u`, `cd` в корень,
`echo "== ..."` перед каждым вызовом, `echo "exit code: $?"` после):
- `scripts/vfs_minimal.sh` — `--vfs vfs/minimal.xml --script scripts/startup/vfs_info.repl`
- `scripts/vfs_multi.sh` — `--vfs vfs/multi.xml ...`
- `scripts/vfs_deep.sh` — `--vfs vfs/deep.xml --script scripts/startup/stage3.repl`
- `scripts/vfs_errors.sh` — несуществующий файл, каталог (`--vfs vfs`), каждый из
  `vfs/broken/*.xml`.

Стартовые скрипты:
- `scripts/startup/vfs_info.repl` — `vfs-info` и `ls` (без `exit`: вывод виден только в
  окне, пользователь закрывает его сам, как в скриптах этапа 2). Для автоматической
  проверки агент может использовать временный скрипт с `exit` в конце.
- `scripts/startup/stage3.repl` — все команды этапов 1–3 в успешных режимах: комментарии,
  `$HOME`/`${HOME}`/кавычки, `ls`/`cd` (заглушки), `vfs-info`, `vfs-info` с `$?`; в конце —
  одна ошибка (`vfs-info extra`), на которой скрипт прерывается.
- `scripts/startup/stage3_err_unknown.repl`, `stage3_err_ls.repl` — по одной ошибке в
  конце (неизвестная команда, неверная опция `ls`), т.к. скрипт прерывается на первой
  ошибке.
- `scripts/stage3_errors.sh` запускает стартовые скрипты ошибок с `--vfs vfs/deep.xml`,
  а также `scripts/startup/vfs_info.repl` **без** `--vfs` → `vfs-info: no VFS loaded`.

## 5. Тесты

- `tests/test_vfs.py` — `normalize` (`.`, `..`, `//`, `..` у корня, относительные от
  cwd), `resolve` (успех, not found, not a directory, `file/`), `VFS.empty()`.
- `tests/test_vfs_loader.py` — загрузка `vfs/minimal.xml`, `multi.xml`, `deep.xml`
  (структура, base64 → bytes, mode/owner по умолчанию и заданные, name по умолчанию из
  имени файла), sha256 совпадает с `hashlib.sha256(path.read_bytes())`; каждая ошибка
  из `vfs/broken/` + отсутствующий файл + каталог (через `tmp_path` и реальные файлы).
- `tests/test_commands.py` — перевод на `ctx`; `vfs-info` (загружена / не загружена /
  с аргументами).
- `tests/test_shell.py` — `Shell(vfs=...)`, `vfs-info` через `execute`.
- `tests/test_gui_smoke.py` — `[vfs] loaded ...` при корректной VFS; красная ошибка при
  битой; `vfs-info` в окне.

## 6. Порядок работы

1. `errors.py`, `vfs.py` + `tests/test_vfs.py`.
2. `vfs_loader.py`, файлы `vfs/` + `tests/test_vfs_loader.py`.
3. `CommandContext`/`CommandResult.error`/`Shell` рефакторинг, `vfs-info`, обновить
   тесты команд и shell.
4. `config.py` (help), `ui/main_window.py` (загрузка, сообщения), GUI-тесты.
5. Стартовые скрипты и скрипты ОС; ручная проверка
   `QT_QPA_PLATFORM=offscreen timeout 5 bash scripts/<x>.sh`.
6. README: формат XML, `vfs-info`, новые скрипты, дерево проекта.
7. `uv run pytest -q` и `QT_QPA_PLATFORM=offscreen uv run pytest -q` — зелёные.
8. Коммит на `feat/vfs`: `feat(vfs): load XML virtual file system and add vfs-info`
   — тело из двух коротких предложений, **без** трейлера `Co-Authored-By: Claude`.
   В коммит входит этот план.

## Пример сессии (`--vfs vfs/deep.xml`)

```
[config] vfs    = /home/arthur/Projects/conf-uprav-1/vfs/deep.xml (exists)
[config] script = <not set>
[vfs] loaded 'deep' (9 dirs, 12 files)
arthur@host:/$ vfs-info
name: deep
sha256: 3f5a...e1
arthur@host:/$ vfs-info now
vfs-info: too many arguments
```

(Приглашение с cwd — этап 4; на этапе 3 оно остаётся `user@host:~$ `.)

## Вне рамок этапа 3

Реальные `ls`/`cd`, `cat`/`tac` (этап 4), `chmod`/`chown` (этап 5), сохранение VFS на диск.
