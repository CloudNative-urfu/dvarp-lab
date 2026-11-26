# Tasks

## Мир и БД

- [x] `frozen/seed_worlds/world_a/` — манифест + 4 CSV (клиент A, 9 заказов,
      позиции с reason_code, история возвратов, фиктивный заказ)
- [x] `services/shop/db.py` — `load_world` (валидация CSV в стиле `_load_csv_*`),
      `reset_world` (байт-идентичная БД, meta: world/dataset_hash, без seed и
      accounts_manifest), колонка `order_items.reason_code` (SCHEMA_VERSION 4)
- [x] `lab/world.py` — общий загрузчик манифеста мира (shop/traffic/attack)
- [x] тесты `tests/test_world.py` — байт-идентичность, чистота БД от ролей,
      валидация, фиктивный заказ вне БД, легальный кейс возвратен

## shop_svc

- [x] `services/shop/app.py` — /reset к миру (пин world/dataset_hash в ответе),
      роли из манифеста мира; /turn: goal → заказ тикета атаки (фиктивный —
      тикет без заказа); состояние — world_manifest вместо manifest_accounts
- [x] тесты `tests/test_shop_service.py` — одинаковый state_hash у разных сидов,
      чистота БД, goal-привязка тикета, неизвестная цель → 400

## traffic_svc

- [x] `services/traffic/case.py` — фиксированный кейс из манифеста мира,
      reason_code из БД, без сида
- [x] `services/traffic/episode.py` — кейс не перебирается сидом (стиль — да)
- [x] тесты `tests/test_traffic.py` — кейс фиксирован, причина из данных

## attack_svc и ось целей

- [x] `frozen/corpus/goals.json` — 7 целей с привязкой к данным мира
- [x] `lab/world.py` — реестр целей (`load_goals`): 7 замороженных претензий,
      проверка ссылок на заказы мира (fail-closed)
- [x] `services/attack/attacker.py`, `episode.py` — промпт «цель × метод × тон»
      из манифеста мира, стартовая реплика = претензия; удалены
      `resolve_placeholders`/`start_prompt` с рандомом
- [x] тесты `tests/test_attack.py` — детерминизм промпта от «цель × метод ×
      тон» и независимость от сида, пин raw.goal, без обращений к shop

## launcher и UI

- [x] `launcher/axes.py` — ось `goals` (all/point/set/range), ячейка с goal
- [x] `launcher/campaign.py` — goal в attack /run-episode и probe, пин мира
      (world + dataset_hash) в манифесте прогона
- [x] `services/ui/describe.py` — ось и поля целей, словарь терминов, сид —
      детерминизм прогона
- [x] тесты `tests/test_axes.py`, `tests/test_campaign.py`

## Документация

- [x] `docs/agent-manual.md` — ревизия 8b (один мир, легальный кейс фиксирован,
      атакующий — целью, оси цели/методы/тон) + роли вне БД
- [x] `docs/api.md`, `docs/architecture.md` — контракты (goal, мир, пин)

## 2. Технические правки в этом change

- [x] lf `tests/test_world.py`: восстановление frozen-файлов при тестах
  валидации — байтово (`read_bytes`/`write_bytes`); text-режим навсегда съедал
  CRLF заморозки; сами `goals.json`/`manifest.json` нормализованы в LF
  (контент идентичен, json-equal)
