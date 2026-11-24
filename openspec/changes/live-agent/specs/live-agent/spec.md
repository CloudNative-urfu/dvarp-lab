## ADDED Requirements

### Requirement: Live defender agent via RESEARCH_LLM_*
shop_svc SHALL строить модель защитника в режиме `live` через канонические
`RESEARCH_LLM_*` (base_url, модель, ключ, параметры), если
`RESEARCH_LLM_BASE_URL` задан в env процесса, и в режиме `stub`
(детерминированный профиль) иначе. Live-режим подчиняется NFR-2.5/2.6:
локальность эндпоинта обходится только при `LAB_ALLOW_REMOTE_LLM=1`
(remote-верификация, не статья); размер модели fail-closed — при
неопределимом по имени размере требуется явный `RESEARCH_LLM_PARAMS_B`.

#### Scenario: Live agent answers via proxy
- **WHEN** эпизод открыт при заданном `RESEARCH_LLM_BASE_URL` и remote-флаге
- **THEN** ответы защитника идут через живую модель; в журнале есть
  `llm_call` события агента

#### Scenario: Unknown size fails closed
- **WHEN** имя модели не содержит размера и `RESEARCH_LLM_PARAMS_B` не задан
- **THEN** сборка live-модели падает с явной ошибкой про
  `RESEARCH_LLM_PARAMS_B`, а не с TypeError

### Requirement: Agent llm_calls reach filter cassettes
Каждый вызов модели защитника SHALL попадать в `raw.llm_calls` записи
filter (пара запрос→ответ) и оседать кассетной строкой `role: agent`;
тексты запросов/ответов идут только в сырую БД filter и наружу через
`/turn` не выходят (барьер «только текст» не тронут). При недоставке записи
буфер не очищается и повторится на следующем ходе.

#### Scenario: Cassette has agent role
- **WHEN** живой эпизод записан в filter
- **THEN** кассета эпизода содержит строки `role: agent` с model пином,
  запросом и ответом

#### Scenario: Barrier holds
- **WHEN** клиент вызвал shop `/turn`
- **THEN** ответ содержит ровно `{text, ended, session_status}` — без
  кассетных текстов
