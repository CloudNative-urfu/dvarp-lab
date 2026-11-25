# Metrics Service — Specification (delta: pin, grid, real frame)

## MODIFIED Requirements

### Requirement: Metrics computed over the raw DB
metrics_svc SHALL считать L*, break-even, detection, экономические
стоимости, queue-член и G-τ из read-only доступа к сырой БД filter_svc.
Базы цен SHALL читаться из пина экономики (`frozen/economics.json`);
чувствительность очереди SHALL публиковаться сеткой ρ₀×p_att (9 ячеек из
сценариев пина) на конфигурацию; L* SHALL публиковаться в двух фреймах:
рабочая валюта — «USD на лаб-эпизод», перевод в реальный фрейм —
зафиксированной потерменной формулой (`real_frame_terms`: refuse/churn ×
(1−p_att)/w_L, attack_service × p_att/w_A, guard/manual без веса,
знаменатель p_att·dV).

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

#### Scenario: G-τ oracle and gate
- **WHEN** легальный эпизод содержит policy-решение
  isolate/escalate/terminate
- **THEN** он считается ложным прерыванием; rate с Wilson 95% CI и гейт
  ≤5% публикуются по config × model_spec; agent-эскалация без policy-
  решения не считается

#### Scenario: Prices follow the pin
- **WHEN** базовые цены в пине экономики меняются
- **THEN** формулы следуют пину (C_manual base = C_human, C_churn = пин,
  границы C_churn = base × факторы пина) при повторном `/compute`

#### Scenario: Queue sensitivity grid
- **WHEN** `/compute` возвращает метрики конфигурации
- **THEN** строка `queue_grid` содержит 9 ячеек ρ₀×p_att (ρ, P_abandon,
  stable) при фиксированных долях эскалаций

#### Scenario: Real-frame L*
- **WHEN** L* рассчитан
- **THEN** рядом публикуется `L_star_real` по сценариям p_att пина —
  потерменный перевод из лаб-фрейма; порядок конфигураций фреймом не
  меняется

### Requirement: Metric storage and aggregation
Результаты SHALL храниться в собственной БД metrics_svc и агрегироваться по
config × model_spec (`GET /metrics/{config_name}`, FR-1.23-style); правка
формул SHALL не требовать перезапуска прогонов.

#### Scenario: Recompute without rerun
- **WHEN** формулы правятся и `/compute` вызывается повторно
- **THEN** новые числа получены из тех же сырых данных без перезапуска
