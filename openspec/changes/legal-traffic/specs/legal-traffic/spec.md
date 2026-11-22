## ADDED Requirements

### Requirement: Frozen conversation styles
Стили общения легального трафика SHALL быть заморожены в `frozen/styles.json`
и применяться по имени: стиль задаёт тон клиента (параметры формулировок),
а не механику возврата. Изменение файла — отдельный осознанный коммит с
дельтой спеки.

#### Scenario: Style by name
- **WHEN** эпизод запрошен со стилем из `frozen/styles.json`
- **THEN** клиент ведёт диалог в заданном тоне; неизвестный стиль — ошибка

### Requirement: Truthful refund cases from shop DB
traffic_svc SHALL собирать правдивый кейс возврата из БД магазина, читая её
только read-only; запись в БД магазина из traffic_svc SHALL быть запрещена.
Кейс детерминирован от сида; каталог товаров от сида не зависит
(инварианты 3 и 8b мануала).

#### Scenario: Deterministic case
- **WHEN** кейс собирается дважды с одним сидом
- **THEN** particulars клиента и раскладка совпадают побайтно

#### Scenario: Read-only access
- **WHEN** traffic_svc обращается к БД магазина
- **THEN** подключение read-only; попытка записи невозможна

## ADDED Requirements

### Requirement: Legal episode loop
traffic_svc SHALL вести эпизод легального трафика: `POST /run-episode`
`{episode_id, config_name, agent_model, style, seed}` →
`{outcome, turns, transcript_ids}`. Каждый ход — через `shop /turn` с
`channel="legal"`; наружу от СС выходит только текст (инвариант 1).

#### Scenario: Episode through shop
- **WHEN** эпизод легального трафика запущен
- **THEN** каждый ход клиента проходит через `shop /turn`, ответ — только текст

### Requirement: Raw recording to filter_svc
Recorder эпизода SHALL пинить `model_spec` в каждой записи и доставлять
сырьё (вызовы модели, `llm_calls`) напрямую в `filter /record` изнутри,
минуя ответ симуляции; кассетная строка формируется на каждую пару
«запрос → ответ» (инварианты 4 и 6).

#### Scenario: Cassette per model call
- **WHEN** клиент (stub или LLM) делает вызов модели
- **THEN** пара «запрос → ответ» попадает в `raw.llm_calls` записи filter

## ADDED Requirements

### Requirement: Records carry config name
Записи легального трафика SHALL пинить имя конфигурации защиты
(`raw.config_name`) — сырая БД остаётся самодостаточной для метрик без
внешнего контекста.

#### Scenario: Config pin in raw
- **WHEN** запись легального эпизода попадает в filter /record
- **THEN** `raw.config_name` совпадает с конфигом ячейки кампании
