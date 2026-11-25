# Metrics Service — Specification (delta: costs)

## MODIFIED Requirements

### Requirement: Metrics computed over the raw DB
metrics_svc SHALL считать L*, break-even, detection и экономические
стоимости из read-only доступа к сырой БД filter_svc
(`POST /compute {config_name, model_spec?}` → `{computed: n}`).
Стоимости защитной стороны SHALL рассчитываться post-hoc из сохранённых
событий (`raw.events`) по замороженному пину экономики
(`frozen/economics.json`): агентные `llm_call` → C_ep, затраты
`guard:*` → C_guard; затраты атакующей стороны SHALL исключаться
(NFR-2.9). Правка пина SHALL менять числа повторным `/compute` без
перезапуска прогонов.

#### Scenario: Compute from stored raw
- **WHEN** `/compute` вызывается после прогонов
- **THEN** метрики посчитаны из сохранённых записей; сырая БД не изменена

#### Scenario: Config filter keeps reference
- **WHEN** `/compute` ограничен подмножеством конфигов
- **THEN** эталонный конфиг ищется по полным данным, L* не вырождается

#### Scenario: Costs from saved events
- **WHEN** в `raw.events` эпизода есть agent `llm_call` и `guard:*`
  записи с `cost`
- **THEN** C_ep/C_guard рассчитаны по тарифам пина экономики и входят в
  расходную сторону L* (`attack_service`, `guard`); затраты компонента
  `attacker` в C_ep/C_guard не входят

#### Scenario: Economics pin is frozen
- **WHEN** пин экономики невалиден (схема/отрицательные тарифы)
- **THEN** расчёт падает с явной ошибкой, а не считает по умолчанию

### Requirement: Metric storage and aggregation
Результаты SHALL храниться в собственной БД metrics_svc и агрегироваться по
config × model_spec (`GET /metrics/{config_name}`, FR-1.23-style); правка
формул SHALL не требовать перезапуска прогонов.

#### Scenario: Recompute without rerun
- **WHEN** формулы правятся и `/compute` вызывается повторно
- **THEN** новые числа получены из тех же сырых данных без перезапуска
