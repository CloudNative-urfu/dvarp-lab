## ADDED Requirements

### Requirement: Single repository layout
dvarp-lab SHALL be a single repository containing the polygon: `services/`
(shop, traffic, attack, filter, metrics — FastAPI apps on local ports
9411–9415), the shared library `lab/`, the script orchestrator `launcher/`,
frozen research characteristics in `frozen/` and pytest tests in `tests/`.
Защита переносится из dvarp-prototype @ `d5828df` как есть, с малой
адаптацией клея; подсистемы прототипа (report_cli, isolation, svckit,
state_store, pay_emu, runner+replay, freeze, Next.js-консоль) не переносятся.

#### Scenario: Layout matches the scheme
- **WHEN** структура каталогов сверяется с `docs/scheme.svg` и мануалом агента
- **THEN** каждая подсистема схемы имеет каталог в репо, лишних подсистем нет

### Requirement: Frozen research characteristics
Характеристики исследования SHALL быть заморожены в `frozen/`:
`configs/*.json` (26 конфигураций защиты) с целостностью по
`configs.lock.json`, `corpus/` (корпус атак с манифестом), `llm.json`
(ростер моделей: name, role, params_b, revision), `styles.json` (стили
общения легального трафика). Файлы frozen меняются редко и осознанно,
отдельным коммитом с дельтой спеки; модели не удаляются из ростера молча.

#### Scenario: Lock detects drift
- **WHEN** содержимое `frozen/configs/*.json` изменяется без обновления lock
- **THEN** проверка целостности конфигураций сообщает об изменённом файле

### Requirement: Shared lab library
`lab/` SHALL предоставлять: `chain` — append-only хеш-цепочку поверх JSONL
(seq, prev, hash; `verify()` возвращает список дефектов), `cassette` — по
строке на пару «запрос → ответ» к модели, `seeds` — детерминированный вывод
сидов, `modelspec` — пин модели и ростер `frozen/llm.json`, `nominal` —
номинальную проверку конфигурации перед прогоном, `db` — SQLite (тесты/dev)
и PostgreSQL (прогоны) через SQLAlchemy, `svc_client` — HTTP-клиент сервисов.

#### Scenario: Chain tamper detection
- **WHEN** строка цепочки перезаписана или удалена
- **THEN** `verify()` возвращает дефект с номером seq; пустой список — цепь цела

#### Scenario: Model pin in every record
- **WHEN** любая запись журнала, сырых данных или манифеста создаётся
- **THEN** она несёт `ModelSpec(name, role, params_b, revision)` из ростера

### Requirement: openspec trace and commit gates
Каждое содержательное изменение SHALL сопровождаться каталогом
`openspec/changes/<change-id>/` (proposal, design, tasks, дельты спек в
`specs/`) в том же коммите, что и код. pre-commit SHALL запускать ruff
(из nixpkgs) и `openspec validate --all`; история коммитов — трейс
разработки, валидный на любом срезе.

#### Scenario: Broken delta rejected
- **WHEN** дельта спеки не проходит `openspec validate --all`
- **THEN** pre-commit отклоняет коммит до записи истории

#### Scenario: History is self-contained
- **WHEN** произвольный коммит истории выписан в отдельное дерево
- **THEN** `openspec validate --all` зелёный: дельты каждого коммита валидны

## ADDED Requirements

### Requirement: Service API contracts document
`docs/api.md` SHALL фиксировать контракты эндпоинтов всех сервисов
(shop, traffic, attack, filter, metrics) и формат спецификации осей
launcher'а. Изменение эндпоинта или формата SHALL сопровождаться правкой
документа в том же коммите.

#### Scenario: Contract documented
- **WHEN** читатель сверяет код сервиса с `docs/api.md`
- **THEN** пути, тела запросов/ответов и порты совпадают

## ADDED Requirements

### Requirement: Lint scope
ruff SHALL линтовать весь код репозитория, кроме замороженных характеристик
(`frozen/`) и ссылочного клона прототипа (`local-sources/`); правило
задаётся в `pyproject.toml`.

#### Scenario: Frozen excluded
- **WHEN** `ruff check` запущен на репозитории
- **THEN** файлы `frozen/` и `local-sources/` не проверяются, остальной код чист
