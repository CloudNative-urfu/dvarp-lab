## Why

Метрики считаются post-hoc (issues #11–#13, #34), но для показа экспертам
(демо, issue #40) не хватает рендера: тепловые карты «конфигурация × метрика»,
break-even по L_viol, реальный фрейм, G-τ с Wilson CI, Pareto «защита ↔ вред».
Рендер — инструмент показа, в измерительный путь не входит.

## What Changes

- `scripts/demo_maps.py` — рендер пяти SVG-карт + `index.html` +
  `metrics_dump.json` из `/metrics/{config}` metrics_svc; без зависимостей
  (голый SVG); группы моделей не схлопываются; remote-прогоны включаются
  предварительным `POST /compute {"include_remote": true}`.

## Capabilities

### New Capabilities
- `demo-maps`: рендер демо-карт метрик скриптом `scripts/demo_maps.py`.

## Impact

- Поведение сервисов не меняется; вне измерительного пути.
