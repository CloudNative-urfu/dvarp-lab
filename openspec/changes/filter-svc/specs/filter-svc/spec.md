## ADDED Requirements

### Requirement: Raw DB on hash chain
filter_svc SHALL хранить сырьё в своей БД: каждая запись
(`POST /record` `{episode_id, channel, turn, text, model_spec, raw,
snapshot}` → `{record_id}`) привязана к строке хеш-цепочки `lab.chain`;
перезапись payload детектируется, запись — только append.

#### Scenario: Chain integrity
- **WHEN** `GET /chain/verify` вызывается после серии записей
- **THEN** дефектов нет; после подмены payload — дефект с номером seq

### Requirement: Text barrier endpoints
Наружные эндпоинты filter_svc SHALL выдавать только тексты:
`GET /text/{episode_id}` возвращает ходы с полями turn/channel/text и без
raw-полей; `GET /chain/verify` — дефекты цепочки. Никакое сырьё не выходит
через наружные эндпоинты (инвариант 1).

#### Scenario: Text endpoint has no raw
- **WHEN** `/text/{episode_id}` прочитан для эпизода с сырьём
- **THEN** в ответе нет полей raw и snapshot — только тексты ходов

### Requirement: Cassette lines
Каждая пара «запрос → ответ» к модели SHALL оседать кассетной строкой
(`lab.cassette`) в записи `raw.llm_calls`; один вызов — одна строка
(инвариант 6).

#### Scenario: Cassette per call
- **WHEN** в записи есть `raw.llm_calls`
- **THEN** каждая строка кассеты — одна пара «запрос → ответ»
