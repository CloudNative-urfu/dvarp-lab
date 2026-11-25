## Why

Аудит перед live-пилотом (2026-11-25, обсуждение с владельцем) выявил два
блокера: (1) код ограничивает модели 8B/12B, тогда как канон (NFR-2.6,
ревизия 2026-11-12) допускает до 16B — модели 12–16B из #84 отклонялись бы;
(2) `/db/readonly` отдаёт connection string наружу (issue #17) — убрать до
любых внешних прогонов, env становится единственным путём traffic_svc к БД.

## What Changes

- `services/shop/llm/settings.py` — единый предел NFR-2.6: 16B
  (SIZE_TARGET_B = 16, исключение 12B удалено, статус `exception_control`
  упразднён);
- `services/shop/app.py` — эндпоинт `GET /db/readonly` удалён;
- `services/traffic/app.py` — `resolve_db_url()`: только
  `LAB_SHOP_DB_URL`, отсутствие env — явная ошибка;
- `docs/api.md`, тесты — соответственно.

## Capabilities

### Modified Capabilities
- `shop-service`: удалён эндпоинт `/db/readonly`;
- `free-llm-endpoints`: политика размера NFR-2.6 — единый предел 16B;
- `shop-guard-stack`: упоминание «модели ≤ 8B» → «≤ 16B».

## Impact

- dev.py/smoke.py уже задают `LAB_SHOP_DB_URL` всем сервисам — путь через
  env не ломает запуск;
- канон не правится (ревизия 2026-11-12 уже в каноне — код отставал).
