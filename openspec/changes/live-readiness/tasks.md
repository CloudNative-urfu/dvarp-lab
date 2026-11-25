# Tasks

## 1. Tasks

- [x] nfr26 `services/shop/llm/settings.py`: единый предел 16B
  (SIZE_TARGET_B=16, SIZE_EXCEPTION_B и статус `exception_control`
  упразднены), docstring ревизован
- [x] readonly `services/shop/app.py`: эндпоинт `GET /db/readonly`
  удалён (issue #17); `services/traffic/app.py`: env — единственный
  путь, отсутствие `LAB_SHOP_DB_URL` — явная ошибка
- [x] docs Строка `/db/readonly` удалена из `docs/api.md`
- [x] tests `test_llm` (16.0 в пределах, 16.5 — отказ, 14B легален),
  `test_shop_service` (тест эндпоинта удалён), `test_attack`
  (forbidden-маркер сохранён)
- [x] spec Дельты: shop-service, free-llm-endpoints, shop-guard-stack

## 2. Validation

- [x] `uv run pytest` — 420 passed
- [x] `openspec validate --all` зелёный
- [x] ruff (check + format) зелёный
