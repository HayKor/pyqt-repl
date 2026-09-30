# План 005 — Этап 5: Дополнительные команды (вариант №4)

> Выполняется после мёржа этапа 4 в `main`, на ветке `feat/chmod-chown` от свежего
> `main`. Перед началом сверить интерфейсы с фактическим кодом этапов 3–4.

## Цель

Команды `chmod` и `chown`, изменяющие метаданные узлов VFS **только в памяти**;
изменения видны через `ls -l`.

## Требования этапа → как закрываем

| # | Требование | Реализация |
|---|------------|------------|
| 1 | `chmod`, `chown` | Классы команд, меняют `VNode.mode` / `owner` / `group` в памяти |
| 2 | Стартовый скрипт со всеми режимами, VFS и ошибками | `scripts/startup/stage5.repl` + `stage5_err_*.repl` + `scripts/stage5.sh` |
| 3 | Коммит | `feat(chmod-chown): ...` на ветке `feat/chmod-chown` |

## 1. Средства

Чистый Python, `re` для разбора символьного режима и `USER[:GROUP]`. Никакой записи на
диск: XML-файл VFS не меняется; `vfs-info` продолжает показывать SHA-256 исходных данных
(хеш источника, задокументировать).

## 2. `chmod [-R] MODE FILE...`

- **Восьмеричный режим**: `^0?[0-7]{3}$` → новые права целиком (`755`, `0644`).
  Спецбиты (setuid/setgid/sticky) не поддерживаются: `4755` → invalid mode.
- **Символьный режим**: список через запятую, каждый элемент
  `[ugoa]*([-+=][rwx]*)+` (например `u+x`, `go-w`, `a=r`, `+x`, `u=rwx,g=rx,o=`,
  `u+x-w`). Пустое «кто» = `a` (umask не применяется — задокументировать). `=` с пустым
  списком прав сбрасывает биты. `X`, `s`, `t`, копирование `u=g` — не поддерживаются →
  invalid mode.
- `-R` — рекурсивно для каталогов (сам каталог и все потомки).
- Ошибки:
  - `chmod: missing operand` (нет аргументов), `chmod: missing operand after '755'`
    (нет файлов) — CommandArgsError, код 2;
  - `chmod: invalid mode: 'xyz'` — код 1 (как GNU);
  - `chmod: cannot access 'x': No such file or directory` / `Not a directory` —
    код 1, остальные файлы обрабатываются;
  - неизвестная опция → `chmod: invalid option -- 'z'`, код 2.
  - Аргумент вида `-x`/`-w` трактуется как режим, если он подходит под символьный
    синтаксис (как GNU: `chmod -x file`), иначе как опция.
- Вывода при успехе нет.

## 3. `chown [-R] OWNER[:GROUP] FILE...`

- Формы: `user`, `user:group`, `user:` (группа не меняется — упрощение, в GNU это
  «группа входа пользователя»; задокументировать), `:group`.
- Имена: `^[a-z_][a-z0-9_-]*$` или число (uid/gid хранится как строка). Пустая
  спецификация / `:` / неверное имя → `chown: invalid user: 'X'` или
  `chown: invalid group: 'X'`, код 1.
- Проверки прав (только root может менять владельца) нет — эмулятор работает от
  «суперпользователя» (задокументировать).
- `-R` — рекурсивно.
- Ошибки операндов и путей — аналогично `chmod` (`chown: missing operand`,
  `chown: cannot access ...`).

## 4. Файлы

```
src/repl/core/modes.py      # НОВЫЙ: parse_mode(spec, current_mode) -> int; ModeError
src/repl/core/commands.py   # ChmodCommand, ChownCommand (+ общий хелпер обхода -R)
tests/test_modes.py         # восьмеричные, символьные, комбинации, ошибки
tests/test_commands.py      # chmod/chown на фикстурной VFS, -R, частичные ошибки,
                            # ls -l отражает изменения; XML-файл на диске не меняется
                            # (сравнить sha256 файла до/после)
tests/test_gui_smoke.py     # chmod + ls -l через окно
scripts/startup/stage5.repl         # все режимы chmod/chown + ls -l до/после, vfs-info
                                    # (хеш не изменился), в конце одна ошибка
scripts/startup/stage5_err_*.repl   # по одной ошибке: invalid mode, нет операнда, нет файла,
                                    # invalid user, invalid group, неизвестная опция
scripts/stage5.sh                   # всё выше с --vfs vfs/deep.xml
README.md
```

## 5. Проверка и коммит

- `uv run pytest -q`, `QT_QPA_PLATFORM=offscreen uv run pytest -q` — зелёные.
- `QT_QPA_PLATFORM=offscreen timeout 5 bash scripts/stage5.sh`; `git status` после
  запусков — `vfs/*.xml` не изменены.
- Коммит на `feat/chmod-chown`:
  `feat(chmod-chown): add in-memory chmod and chown commands`
  — тело из двух коротких предложений, **без** трейлера `Co-Authored-By: Claude`.
  В коммит входит этот план.

## Вне рамок

Проверка прав доступа при `cat`/`cd`/`ls`, спецбиты, сохранение изменённой VFS.
