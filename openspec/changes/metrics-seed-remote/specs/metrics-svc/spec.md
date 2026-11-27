## MODIFIED Requirements

### Requirement: Metric storage and aggregation
metrics_svc SHALL хранить результаты по config × model_spec × mode
(`local`, `remote`, `all`), не смешивая источники без явного выбора,
и SHALL сообщать `n_remote` в каждом агрегате.

#### Scenario: Remote compute
- **WHEN** `/compute` вызывается с `include_remote=true`
- **THEN** local и remote строки разделены, а общий расчёт имеет `mode=all`

#### Scenario: Default compute
- **WHEN** `/compute` вызывается без include_remote
- **THEN** сохраняются только local строки, remote-эпизоды не участвуют

### Requirement: Seed spread by run and seed
metrics_svc SHALL вычислять V, R, L* и статус для каждой пары `(run_id, seed)`
по одной конфигурации и модели и SHALL отдавать `seed_spread` в `/preview`
и `metric_results`. Сид живого LLM SHALL считаться меткой вариативности,
а не гарантией воспроизводимости.

#### Scenario: Several seeds in one run
- **WHEN** кампания содержит несколько сидов с одинаковым run_id
- **THEN** у каждого сида отдельные V, R, L* и статус; разброс охватывает все группы

#### Scenario: Reference of the same seed
- **WHEN** g0 не имеет эпизодов того же run_id, seed и mode
- **THEN** у соответствующей группы статус `no_reference` и L* отсутствует
