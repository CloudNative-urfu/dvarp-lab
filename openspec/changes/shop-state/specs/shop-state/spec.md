## ADDED Requirements

### Requirement: Unified event and cost journal
Сервис магазина SHALL вести единый журнал событий и затрат (FR-1.17) с
по-сторонним учётом: компоненты пишут только через `ComponentWriter`,
полученный от `EventLog.writer(name)`; сторона записи берётся из реестра
`COMPONENT_SIDES`. Эпизоды открывает и закрывает оркестратор
(`start_episode`/`end_episode`); событие с незакрытым или не открытым
эпизодом SHALL отклоняться, чтобы затраты не перетекали между эпизодами.

#### Scenario: Writer is write-only
- **WHEN** компонент пытается читать журнал или изменить свой writer
- **THEN** доступ запрещён: writer иммутабелен и write-only

#### Scenario: Costs stay inside the episode
- **WHEN** событие пишется вне открытого эпизода
- **THEN** журнал отклоняет событие с ошибкой схемы

### Requirement: Append-only journal storage
Журнал SHALL храниться построчно в JSONL на хеш-цепочке `lab.chain`
(seq/prev/hash): редактирование, удаление или переупорядочение сохранённой
строки SHALL детектироваться `verify_chain`; запись ведётся только в конец.

#### Scenario: Tamper detected
- **WHEN** строка журнала перезаписана, удалена или переставлена
- **THEN** `verify_chain` возвращает дефект; целая цепочка даёт пустой список

## ADDED Requirements

### Requirement: Reproducibility primitives
`services/shop/repro.py` SHALL предоставлять примитивы воспроизводимости:
`canonical_json` (каноническая сериализация), `strip_volatile` (исключение
волатильных измерений: ts, wall_ms, cpu_ms, gpu_ms…), `trajectory_fingerprint`
(отпечаток траектории без временных меток) и `plan_contract` (контракт плана
прогона). Повтор эпизода с тем же сидом SHALL давать совпадающие отпечатки
(NFR-2.2/2.3).

#### Scenario: Trajectory fingerprint stable
- **WHEN** эпизод повторён с тем же сидом
- **THEN** отпечаток траектории совпадает: волатильные измерения исключены
