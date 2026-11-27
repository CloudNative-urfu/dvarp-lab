## Why

Issue [#42](https://github.com/CloudNative-urfu/dvarp-lab/issues/42): launcher не передаёт
флаги расчёта, повторные сиды не видны в метриках, remote смешивается с local.

## What Changes

- CLI/launcher передают `include_remote` и `include_probe` в `/compute`;
- расчёт группирует эпизоды по `(run_id, seed)`, сравнивает L* с g0 того же
  сида и режима, публикует `seed_spread` в preview и metric_results;
- metric_results хранит `mode`, агрегат — `n_remote`, а UI различает режимы;
- документирован общий `LAB_RUNS_DIR` / `LAB_RAW_DB_URL` для всех процессов.

## Capabilities

### Modified Capabilities

- `metrics-svc`: повторные сиды и раздельные режимы расчёта.
- `launcher-campaign`: явные флаги расчёта и исходный сид группы.

## Impact

Сырая БД не меняется. Существующая metrics.db получает колонку mode при первом
обращении; новые строки режима различимы после пересчёта.
