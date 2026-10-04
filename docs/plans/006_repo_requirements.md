# План 006 — Оформление репозитория по требованиям (`docs/requirements.pdf`)

> Ветка `chore/repo-requirements` от свежего `main`. Поведение эмулятора не меняется:
> все тесты (`QT_QPA_PLATFORM=offscreen uv run pytest -q`) должны проходить до и после.

## Результаты проверки

Язык — Python, поэтому применимы правила С1–С6, Г1–Г5, Р1, Р2, Р6, Ф1, А1, К1, Ц1,
М1, И1.

| # | Правило | Состояние | Что делаем |
|---|---------|-----------|------------|
| С1–С4 | README.md, .gitignore, src, tests | есть | — |
| С5 | `run.sh` / `run.bat` / `Makefile` в корне | **нет** | добавить `run.sh` и `Makefile` |
| С6 | Conventional Commits | `Initial commit`, `feat/chmod-chown (#5)`, `Chore/beautify (#6)` | историю не переписываем (решение пользователя); новые коммиты — конвенциональные |
| Г1, Г3, Г4 | архивы, служебные файлы Python, артефакты сборки | нет | дополнить `.gitignore` (`.pytest_cache/`, `.ruff_cache/`) |
| Г2, Р1 | бинарные файлы, файлы >1000 строк | `docs/task.pdf` (PDF, 2742 «строки») | `git rm --cached docs/task.pdf`, `docs/*.pdf` в `.gitignore` (файлы остаются локально) |
| Г5 | настройки редактора | нет | `.idea/`, `.vscode/`, `*.swp` в `.gitignore` на будущее |
| Р2 | строки >80 символов в `.py` | 96 строк (17 в `src`, 79 в `tests`) | переносить |
| Ф1 | функции >40 строк | `LsCommand.run` (56), `parser.tokenize` (82), `tests/test_commands.make_vfs` (52) | разбить |
| А1 | >7 аргументов | нет | — |
| К1 | комментарии вместо docstring | нет docstring у модулей/классов/публичных методов в `src`; комментарии над `def` (`_human_size`, `_tac_records`, `_walk`, `_parse_owner_spec`) | docstrings |
| Ц1 | цикломатическая сложность >10 | `tokenize` (20), `LsCommand.run` (15), `ChownCommand.run` (11) | разбить |
| М1 | магические числа в сравнениях | 2 в `src` (`1024`, `10` в `_human_size`), 49 в `tests` | константы |
| И1 | PEP8-имена | `_InvalidOwnerSpec` (исключение без суффикса `Error`) | `_InvalidOwnerSpecError` |
| README | общее описание, все функции/настройки, сборка и тесты, примеры | нет явных разделов «Сборка» и «Примеры использования» | дописать |

## 1. Линтер как источник истины

`uv add --dev ruff`, в `pyproject.toml`:

```toml
[tool.ruff]
line-length = 80
src = ["src", "tests"]

[tool.ruff.lint]
preview = true
select = ["E", "F", "W", "C901", "N", "D", "PLR0913", "PLR0917", "PLR2004"]
ignore = ["D203", "D213"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 7
max-positional-args = 7

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D102", "D103"]   # test_* имена говорят сами за себя
```

Также `description` в `pyproject.toml` (сейчас `Add your description here`) заменить
на реальное описание.

Цель: `uv run ruff check` выдаёт 0 замечаний **без `# noqa`**. Длину функций ruff не
проверяет, поэтому дополнительно: ни одной функции >40 строк (от `def` до последней
строки тела включительно), в том числе в тестах.

## 2. `run.sh` и `Makefile` (С5)

- `run.sh` (исполняемый, `#!/usr/bin/env bash`, `set -euo pipefail`) запускает
  `uv run repl "$@"` из каталога скрипта.
- `Makefile` с целями `install` (`uv sync`), `run` (`./run.sh $(ARGS)`), `test`
  (`QT_QPA_PLATFORM=offscreen uv run pytest -q`), `lint` (`uv run ruff check`),
  `build` (`uv build`), `clean` (удалить `dist/`, `.pytest_cache/`, `.ruff_cache/`,
  `__pycache__`); `.PHONY` для всех.

## 3. Код `src/`

- Docstrings (PEP 257, по-английски, как текущие комментарии): у каждого модуля,
  пакета (`__init__.py`), публичного класса, публичного метода/функции и `__init__`.
  Комментарии над `def` (`_human_size`, `_tac_records`, `_walk`, `_parse_owner_spec`)
  перенести в docstring этой функции. Строчные комментарии внутри тел функций,
  поясняющие отдельную строку, можно оставить.
- Docstring `Command.run` «raises CommandArgsError on bad args» → в повелительном
  наклонении с заглавной буквы.
- Коды возврата: в `core/errors.py` добавить `EXIT_OK = 0`, `EXIT_FAILURE = 1`,
  `EXIT_USAGE = 2`, `EXIT_NOT_FOUND = 127` и использовать их вместо литералов в
  `shell.py`, `commands.py` и т.д.
- `_human_size`: `1024` → `_SIZE_STEP`, `10` → `_ONE_DECIMAL_BELOW` (или похожие имена).
- `parser.tokenize`: разбить на вспомогательные функции (например, обработка
  одинарных кавычек, двойных кавычек, `$`-подстановки, `\`), каждая ≤40 строк и
  сложность ≤10. Поведение и сообщения об ошибках — без изменений.
- `LsCommand.run`: вынести разбор опций и раздельную обработку файлов/каталогов в
  помощники; ≤40 строк, сложность ≤10.
- `ChownCommand.run`: снизить сложность до ≤10 (например, общий помощник для
  разбора `-R` и операндов с `ChmodCommand`, если это естественно).
- `_InvalidOwnerSpec` → `_InvalidOwnerSpecError`.

## 4. Тесты `tests/`

- Docstring у каждого модуля тестов и у вспомогательных функций/фикстур (не `test_*`).
- `make_vfs` в `test_commands.py` (52 строки) — сократить до ≤40, например собрать
  дерево из XML-строки через `load_vfs`-совместимый путь или разбить на помощники.
- Магические числа в сравнениях:
  - коды возврата — `EXIT_USAGE`/`EXIT_NOT_FOUND`/… из `repl.core.errors`;
  - права (`== 0o755` и т.п.) — сравнивать строковое представление через помощник
    вроде `perms(mode) -> "rwxr-xr-x"` (`stat.filemode(mode)[1:]`); строки ruff
    магическими не считает, а читается это лучше восьмеричных чисел;
  - прочие (`len(...) == 3`) — сравнивать со списком/строкой целиком или вводить
    именованную константу.
- Строки >80 — переносить.

## 5. `.gitignore` и бинарники

Добавить `.pytest_cache/`, `.ruff_cache/`, `.idea/`, `.vscode/`, `*.swp`,
`docs/*.pdf`. `git rm --cached docs/task.pdf` (локальная копия остаётся).

## 6. README

Привести к четырём требуемым пунктам, не теряя существующего текста:

1. Общее описание (есть — расширить на 1–2 предложения о назначении).
2. Описание всех функций и настроек — существующие разделы «Параметры запуска»,
   «Стартовый скрипт», «Виртуальная файловая система», «Команды» (сгруппировать
   под общим заголовком, если это естественно).
3. «Сборка и тесты»: `uv sync` / `make install`, `uv build` / `make build`,
   `uv run pytest` / `make test`, `make lint`.
4. «Примеры использования»: `./run.sh`, `./run.sh --vfs vfs/deep.xml --script
   scripts/startup/stage4.repl`, `make run ARGS="..."`, плюс короткий пример сеанса
   (`ls -l`, `cd`, `cat`, `chmod`) с выводом — вывод снять реальным запуском или из
   тестов, не выдумывать.

В «Структуре проекта» добавить `run.sh`, `Makefile`, `docs/plans/`.

## 7. Проверка

- `uv run ruff check` — 0 замечаний, `grep -rn noqa src tests` — пусто.
- Скрипт проверки длины функций (AST, `end_lineno - lineno + 1 <= 40`) по всем `.py`.
- `QT_QPA_PLATFORM=offscreen uv run pytest -q` — всё зелёное, число тестов не
  уменьшилось.
- `./run.sh --help` и `make test` работают.
- `git ls-files` — нет PDF.

## 8. Коммиты

Conventional Commits, тело — около двух предложений, без трейлера Co-Authored-By.
Например: `chore(repo): add run.sh, Makefile and ruff config`,
`refactor(core): split long functions and add docstrings`,
`test: replace magic numbers and wrap long lines`, `docs(readme): add build and usage
sections`. Не пушить. PR-заголовок при мёрже — тоже в формате `type(scope): ...`.
