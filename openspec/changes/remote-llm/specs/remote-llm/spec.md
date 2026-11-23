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

## ADDED Requirements

### Requirement: Live OpenAI-compatible client
Живой клиент SHALL подключаться к OpenAI-совместимому прокси: base_url +
модель + Bearer-ключ в env процесса (`LAB_CUSTOMER_LLM_*`,
`LAB_ATTACKER_LLM_*`; у агента — канонические `RESEARCH_LLM_*` с
`LAB_ALLOW_REMOTE_LLM=1`); model+bearer подставляются в traffic/attack,
shop-настройки LLM получают remote-bypass. Ключи не попадают в журнал,
манифесты и кассеты.

#### Scenario: Live traffic and attack
- **WHEN** traffic/attack запущены с LAB_*_LLM_настройками
- **THEN** ходы идут через живую модель с Bearer-ключом из env; кассеты
  пишутся как обычно, ключей в них нет

#### Scenario: Remote bypass in shop settings
- **WHEN** remote-проверка включена (allow_remote_llm)
- **THEN** shop LLM settings допускают не-localhost base_url, агент —
  канонические RESEARCH_LLM_* переменные

### Requirement: Nominal check for live endpoints
Номинальная проверка SHALL различать локальные и remote эндпоинты и
использовать выбранные клиентом настройки (base_url прокси), не требуя
127.0.0.1 для живого прокси при включённом флаге.

#### Scenario: Proxy endpoint accepted
- **WHEN** клиент настроен на прокси с флагом allow_remote_llm
- **THEN** номинальная проверка проходит по настройкам клиента
