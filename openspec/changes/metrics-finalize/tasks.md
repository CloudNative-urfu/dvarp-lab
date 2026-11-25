# Tasks

## 1. Tasks

- [x] pin Секция `queue.rho0_scenarios` в пине + валидация (base_rho в сетке)
- [x] formulas Базы цен из пина (`price_ranges`/`base_prices`/`bound_prices`)
- [x] grid `queue_grid` (9 ячеек) в `extract` + строка в `/metrics`
- [x] frame Фрейм A: `real_frame_terms` + `l_star_real`, строка `L_star_real`
  (3 сценария p_att); защита от вырожденных w_A/w_L
- [x] cleanup `services/shop/manual_queue/analytic.py` удалён; README,
  docstring'и `__init__`/`model.py` поправлены
- [x] tests пин-следование, сетка (9 ячеек), потерменное масштабирование,
  L*_real golden, порядок конфигураций неизменен
- [x] spec Дельта спеки (`specs/metrics-svc/spec.md`)

## 2. Validation

- [x] `uv run pytest` — 426 passed
- [x] `openspec validate --all` зелёный
- [x] ruff (check + format) зелёный
