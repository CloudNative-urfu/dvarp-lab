## Why

Симуляции ходят текстом; СС нужен сервисный фасад: сброс/конфигурация БД,
ход агента, снимки состояния, read-only доступ для traffic_svc. Эндпоинты
становятся контрактом кампании (launcher вызывает их в фиксированном
порядке).

## What Changes

- `services/shop/app.py` — FastAPI-приложение shop_svc: `POST /reset`,
  `POST /configure`, `POST /turn`, `GET /snapshot/{id}`,
  `POST /snapshot/restore`, `GET /db/readonly`.

## Capabilities

### New Capabilities
- `shop-service`: сервисный фасад СС — reset/configure/turn/snapshot и
  барьер «только текст» на /turn.

### Modified Capabilities
<!-- none: новая подсистема -->

## Impact

- симуляции и launcher получают единый вход в СС (порт 9411);
- сырьё доставляется в filter_svc изнутри app, минуя ответ /turn.
