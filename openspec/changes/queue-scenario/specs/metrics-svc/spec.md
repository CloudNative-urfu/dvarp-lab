# Metrics Service — Specification (delta: analytic queue)

## MODIFIED Requirements

### Requirement: Metrics computed over the raw DB
metrics_svc SHALL считать L*, break-even, detection, экономические
стоимости и **queue-член** из read-only доступа к сырой БД filter_svc.
Queue-член SHALL рассчитываться аналитической моделью (Эрланг C
рекурсией Эрланга B) из долей эскалаций сохранённых финалов
(E_A/E_L раздельно) и параметров пина экономики (`frozen/economics.json`):
базовая загрузка ρ₀, якорь масштаба (операторы/разбор/терпение), ревейт
долей на реалистичный микс через p_att. Отвал SHALL выводиться из
экспоненциального терпения поверх `P_wait` (канон dvarp#39); цена ухода
C_churn SHALL применяться формулами (чувствительность ±×2). Никакой
симуляции в рантайме; правка параметров модели SHALL менять числа
повторным `/compute` без перезапуска прогонов.

#### Scenario: Compute from stored raw
- **WHEN** `/compute` вызывается после прогонов
- **THEN** метрики посчитаны из сохранённых записей; сырая БД не изменена

#### Scenario: Config filter keeps reference
- **WHEN** `/compute` ограничен подмножеством конфигов
- **THEN** эталонный конфиг ищется по полным данным, L* не вырождается

#### Scenario: Queue member from analytic model
- **WHEN** у конфигурации ненулевая доля легальных эскалаций (E_L > 0)
- **THEN** queue-член (отвал) входит в числитель L*; при ρ ≥ 1 очередь
  помечается нестабильной и член считается нулём с явным флагом

#### Scenario: Reweighting to realistic mix
- **WHEN** доли эскалаций E_A/E_L из лаб-микса (w_A = 0.5) подставляются
  в очередь
- **THEN** нагрузка считается от ревейтнутой доли
  `p_att·E_A + (1−p_att)·E_L`, а не напрямую от лаб-микса

### Requirement: Metric storage and aggregation
Результаты SHALL храниться в собственной БД metrics_svc и агрегироваться по
config × model_spec (`GET /metrics/{config_name}`, FR-1.23-style); правка
формул SHALL не требовать перезапуска прогонов.

#### Scenario: Recompute without rerun
- **WHEN** формулы правятся и `/compute` вызывается повторно
- **THEN** новые числа получены из тех же сырых данных без перезапуска
