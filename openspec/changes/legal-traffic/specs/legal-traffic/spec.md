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
