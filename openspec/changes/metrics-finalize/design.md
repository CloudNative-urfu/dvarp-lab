# Design — metrics-finalize

## Фрейм A (решение владельца 2026-11-25)

Рабочая валюта всех термов ΔNet — «USD на лаб-эпизод» (w_A/w_L лаб-микса).
Перевод в реальный фрейм — потерменный (не общий множитель: guard/manual не
имеют долевого веса):

```
refuse_real  = refuse  × (1 − p_att)/w_L
churn_real   = churn   × (1 − p_att)/w_L
attack_real  = attack_service × p_att/w_A
guard_real   = guard;  manual_real = manual
L*_real      = Σnum_real / (p_att·dV)
```

Порядок сравнения конфигураций фреймом не меняется (проверено тестом);
абсолютный L* — на реальном знаменателе (атаки редки → порог выше ~×30 при
p_att = 3%). Частичные данные (одна нога) — множители 1.0 (термы нулевые).

## Пин → формулы

`base_prices(pin)` / `price_ranges(pin)` читают `frozen/economics.json`:
C_manual base = C_human, C_churn = пин, границы C_churn = base ×
price_sensitivity_factors (±×2). C_refuse и верх C_manual — §9.4
(декомпозиция break-even, не пин). Тест «пин изменился → формулы следуют».

## Сетка ρ₀×p_att

`queue_grid`: 9 ячеек {ρ₀ ∈ [0.3, 0.6, 0.7]} × {p_att ∈ [0.01, 0.03, 0.1]}
на конфигурацию при фиксированных долях эскалаций — закрывает заявленную в
validity.md сетку. Ячейка: ρ, P_abandon, stable.

## Stale analytic.py

`services/shop/manual_queue/analytic.py` удалён: дублировал
`metrics/queue.py` со старыми non-claims («abandonment не моделируется») и
сеткой K×S. `CaseRecord`/`DISCIPLINES` (нужны замороженному коду защиты) и
DES-модель (проверка формул в тестах) сохранены.
