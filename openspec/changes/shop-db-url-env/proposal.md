## Why

Issue: [CloudNative-urfu/dvarp-lab#17](https://github.com/CloudNative-urfu/dvarp-lab/issues/17).

Shop `GET /db/readonly` отдавал полную строку подключения к БД магазина по HTTP
любому процессу на хосте. На SQLite в ней нет кредов, но на сервере прогонов с
PostgreSQL ушёл бы `user:pass`. traffic_svc держал эндпоинт как запасной путь,
хотя первым читает env `LAB_SHOP_DB_URL`.

## What Changes

- **BREAKING** `GET /db/readonly` удалён из shop_svc (теперь 404);
- traffic_svc берёт строку подключения только из env `LAB_SHOP_DB_URL`; без
  неё `/run-episode` отвечает 400 с понятной ошибкой, к shop_svc за строкой не
  ходит;
- `docs/api.md`, README: строка подключения — секрет конфигурации, по HTTP не
  отдаётся.

## Capabilities

### New Capabilities
- `shop-db-url-env`: строка подключения к БД магазина живёт только в env.

### Modified Capabilities
<!-- shop-service: из списка эндпоинтов уходит GET /db/readonly -->

## Impact

- `scripts/dev.py` и `scripts/smoke.py` уже задают `LAB_SHOP_DB_URL` всем
  сервисам — запуск не меняется;
- барьерный тест атакующего (`/db/readonly` в запрещённых маркерах) остаётся
  как есть.
