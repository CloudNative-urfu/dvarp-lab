## Why

Остаток аудита live-readiness (issue #34): базы цен захардкожены в формулы
при живом пине экономики; сетка чувствительности ρ₀×p_att заявлена в
`docs/validity.md`, но не реализована; принятый фрейм A («рабочая валюта —
лаб-эпизод, перевод в реальный фрейм — явной потерменной формулой») не
зафиксирован кодом; stale `manual_queue/analytic.py` дублирует очередь со
старыми non-claims.

## What Changes

- `formulas.py` — базы цен из пина (`base_prices(pin)`, `price_ranges`):
  C_manual base = C_human, C_churn = пин, границы C_churn = base × факторы
  пина; C_refuse — §9.4;
- `frozen/economics.json` — `queue.rho0_scenarios [0.3, 0.6, 0.7]`
  (валидация: base_rho ∈ сетке);
- `extract.py` — `queue_grid`: 9 ячеек (ρ₀×p_att) на конфигурацию, строка
  `queue_grid`;
- `formulas.py` — фрейм A: `real_frame_terms` (потерменные множители
  (1−p_att)/w_L и p_att/w_A) и `l_star_real`; строка `L_star_real`
  (3 сценария p_att) рядом с лабовым L*;
- `services/shop/manual_queue/analytic.py` удалён (аналитика — в
  `metrics/queue.py`); README/docstring-ссылки поправлены.

## Capabilities

### Modified Capabilities
- `metrics-svc`: цены следуют пину экономики; чувствительность очереди
  ρ₀×p_att публикуется; перевод в реальный фрейм — зафиксированная
  потерменная формула.

## Impact

- golden-базы не меняются (пин согласован с прежними хардкодами);
- канон-правка дренажа (λ_Q → λ) — отдельный PR в `dvarp` (не спека лаба).
