## Why

Метрики канона (L*, break-even, detection) должны считаться поверх
сохранённых сырых данных, а не в процессе прогона: «сбор ≠ расчёт»
(инвариант 7). Отдельный сервис позволяет пересчитывать формулы когда
угодно — правка формул не требует перезапуска прогонов.

## What Changes

- `services/metrics/formulas.py` — формулы канона: L*, break-even,
  detection;
- `services/metrics/extract.py` — извлечение эпизодов и группировка из
  сырой БД (read-only);
- `services/metrics/models.py` — строки результатов;
- `services/metrics/app.py` — `POST /compute`, `GET /metrics/{config_name}`;
- `tests/test_metrics_golden.py` (золотые значения), `tests/test_metrics_service.py`.

## Capabilities

### New Capabilities
- `metrics-svc`: расчёт метрик канона поверх сырой БД, собственное
  хранилище результатов, агрегация по config × model.

### Modified Capabilities
<!-- none: новая подсистема -->

## Impact

- launcher и консоль получают точки `/compute` и `/metrics`;
- сервисы прогона (shop/traffic/attack/filter) остаются без метрик.
