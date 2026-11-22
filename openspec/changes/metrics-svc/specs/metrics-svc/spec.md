## ADDED Requirements

### Requirement: Metrics computed over the raw DB
metrics_svc SHALL считать L*, break-even и detection из read-only доступа к
сырой БД filter_svc (`POST /compute {config_name, model_spec?}` →
`{computed: n}`). В сервисах прогона (shop/traffic/attack/filter) метрик
нет — всё вычисление только здесь (инвариант 7).

#### Scenario: Compute from stored raw
- **WHEN** `/compute` вызывается после прогонов
- **THEN** метрики посчитаны из сохранённых записей; сырая БD не изменена

#### Scenario: Config filter keeps reference
- **WHEN** `/compute` ограничен подмножеством конфигов
- **THEN** эталонный конфиг ищется по полным данным, L* не вырождается

### Requirement: Metric storage and aggregation
Результаты SHALL храниться в собственной БД metrics_svc и агрегироваться по
config × model_spec (`GET /metrics/{config_name}`, FR-1.23-style); правка
формул SHALL не требовать перезапуска прогонов.

#### Scenario: Recompute without rerun
- **WHEN** формулы правятся и `/compute` вызывается повторно
- **THEN** новые числа получены из тех же сырых данных без перезапуска
