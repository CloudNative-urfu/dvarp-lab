## ADDED Requirements

### Requirement: Off-roster model names in remote verification
При включённом remote-режиме имя модели вне ростера `frozen/llm.json`
SHALL допускаться во всех точках входа прогона: shop `/configure`
(при `LAB_ALLOW_REMOTE_LLM=1` в env shop-процесса), attacker-модель
кампании, `probe()` (агент и атакующий) и `set`-режим модельных осей.
Пин — честный model_spec с `params_b=None` и `revision="remote-verification"`.
Без remote-флага поведение прежнее: off-roster отвергается.

#### Scenario: Campaign with external attacker model
- **WHEN** кампания с `allow_remote_llm` и attacker-моделью вне ростера
- **THEN** ячейка содержит attacker_model с пином remote-verification и
  прогон проходит номинальную проверку

#### Scenario: Probe with external model
- **WHEN** probe вызван с off-roster agent_model и remote-флагом
- **THEN** эпизод запускается; без remote-флага — отказ по ростеру

#### Scenario: Set-mode accepts external names
- **WHEN** ось agent_models в режиме `set` содержит имена вне ростера с
  remote-флагом
- **THEN** значения принимаются; для не-модельных осей `set` по-прежнему
  требует значения из frozen

### Requirement: UI shows remote model names from env
`/api/meta` ui_svc SHALL включать `remote_models` — имена из env процесса
(`RESEARCH_LLM_MODEL` для агента, `LAB_ATTACKER_LLM_MODEL` для атакующего),
`null` если не заданы; ключи и base_url не раскрываются никогда. Форма
запуска при включённой галочке Remote LLM подставляет эти имена в поля
моделей; форма Probe пробрасывает `allow_remote_llm` в launcher.

#### Scenario: Prefill from env
- **WHEN** remote-галочка включена и env содержит имена моделей
- **THEN** поля «Модель агента»/«Модель атакующего» предзаполнены этими
  именами

#### Scenario: No secrets in meta
- **WHEN** `/api/meta` отвечен
- **THEN** в ответе нет значений `*_API_KEY` и `*_BASE_URL`
