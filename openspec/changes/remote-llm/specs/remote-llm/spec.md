## ADDED Requirements

### Requirement: allow_remote_llm verification flag
Флаг `allow_remote_llm` SHALL быть единственным способом обойти локальность
LLM-эндпоинтов, и только для проверки работоспособности (прокси и т.п.),
никогда для данных статьи (NFR-2.4/2.5): номинальная проверка допускает
remote-эндпоинты лишь с флагом; флаг задаётся в спецификации осей
(`/ CLI --allow-remote-llm`, галочка в UI).

#### Scenario: Remote blocked by default
- **WHEN** прогон с remote-эндпоинтом без флага
- **THEN** номинальная проверка падает, кампания не стартует

#### Scenario: Flag visible in spec
- **WHEN** прогон запущен с флагом
- **THEN** решение зафиксировано в спецификации осей прогона

### Requirement: Triple remote guard
Remote-прогоны SHALL пиниться тройным guard-ом: пин `"remote_llm": true` в
манифесте прогона; `raw.remote_llm=true` в каждой записи filter; метрики
пропускают remote-эпизоды по умолчанию (`include_remote` — явная опция
`/compute`). Remote-модели вне ростера получают честный model_spec с
`revision="remote-verification"`.

#### Scenario: Manifest pin
- **WHEN** remote-прогон записан
- **THEN** манифест содержит `"remote_llm": true`

#### Scenario: Raw pin
- **WHEN** запись remote-эпизода попала в filter
- **THEN** `raw.remote_llm` равен true

#### Scenario: Metrics skip remote
- **WHEN** `/compute` вызван без include_remote
- **THEN** remote-эпизоды не входят в метрики; с явным include_remote —
  входят (для проверки формул на живом материале)
