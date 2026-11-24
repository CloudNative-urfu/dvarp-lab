## Why

Issue: [CloudNative-urfu/dvarp-lab#2](https://github.com/CloudNative-urfu/dvarp-lab/issues/2).

Консоль (`services/ui/static`, ~670 строк vanilla) неудобна и неполна: оси
без `set`-режима, пресеты и легенда захардкожены в JS, нет вкладки прогонов
с деталями ячеек, нет одноразового расчёта метрик по фильтрам, `/api/compute`
терял `include_remote`, а трейс показывал только ответы агента, причём
задвоенными (запись shop + запись симуляции).

## What Changes

- `services/ui/describe.py`: оси (режимы, юниверсы, дефолты), поля запуска и
  probe, пресеты smoke/пилот, словарь терминов — данными; `/api/meta` отдаёт их;
- фронт переписан на vendored Vue (`static/vendor/vue.global.prod.js`, MIT,
  без node/билда): универсальный рендер формы, все режимы осей включая `set`,
  вкладки Запуск / Прогоны / Трейс / Метрики / Система, тултипы на всех ключах;
- `ui`: `/api/runs` (сводка), `/api/runs/{run_id}` (манифест), `/api/preview`,
  `/api/metric-models`, `/api/dialog/{id}`; `/api/compute` пробрасывает все
  фильтры; `/api/metrics/{config}` раскладывает строки по model_spec;
- `metrics_svc`: read-only `POST /preview` (расчёт без записи + собранные
  агрегаты) и `GET /models`; `compute` разделён на расчёт и запись;
- `filter_svc`: `GET /dialog/{id}` — диалог из сообщений канала, только тексты.

## Capabilities

### New Capabilities
- `console-rework`: data-driven консоль, одноразовый расчёт метрик, диалог эпизода.

### Modified Capabilities
<!-- console-ui: фронт заменён целиком (см. design) -->

## Impact

- инварианты 8a (UI — читатель/вызыватель), 7 (сбор ≠ расчёт: preview не пишет),
  1 (барьер: /dialog — только тексты канала) сохраняются;
- старый vanilla-фронт удалён; `allow_remote_llm` в форме не нужен (#7).
