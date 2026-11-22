## Why

Барьер «только текст» — центральный принцип полигона: наружу от СС выходит
только текст ответа, а сырьё (решения гвардрейлов, вызовы инструментов,
llm_calls, снимки состояния) накапливается отдельно — это и есть измеряемые
данные исследования. Отдельный сервис фильтрации держит барьер
архитектурно, а не на честном слове.

## What Changes

- `services/filter/store.py` — сырая БД (SQLite dev / PostgreSQL прогоны)
  под записями на строке хеш-цепочки `lab.chain`;
- `services/filter/models.py` — модель записи (episode, channel, turn, text,
  model_spec, raw, snapshot);
- `services/filter/app.py` — эндпоинты `/record`, `/text/{episode_id}`,
  `/chain/verify`;
- `tests/conftest.py`, `tests/test_filter_service.py`.

## Capabilities

### New Capabilities
- `filter-svc`: сырая БД с хеш-цепочкой, кассеты и барьер «только текст» на
  эндпоинтах.

### Modified Capabilities
<!-- none: новая подсистема -->

## Impact

- shop/traffic/attack получают адрес доставки сырья (изнутри сервисов);
- метрики будут читаться из сырой БД read-only (`metrics-svc`).
