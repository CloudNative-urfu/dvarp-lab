## Why

Вердикт о судьбе обращения — измеряемая точка эксперимента: он должен
строиться из структурных записей (журнал, БД, инструменты), а не из слов
агента, иначе метрики станут самосвидетельством защиты. Переносится
оценщик прототипа (FR-1.18/1.19).

## What Changes

- `services/shop/evaluator/evaluator.py` — вердикт по структурным записям;
- `services/shop/evaluator/evidence.py` — сбор доказательств;
- `services/shop/evaluator/state.py` — дифференциальное состояние БД;
- `services/shop/evaluator/prompt_leak.py` — детектор утечки промпта;
- `services/shop/evaluator/harness.py` — каркас прогонов оценщика.

## Capabilities

### New Capabilities
- `shop-evaluator`: вердикт и доказательства из структурных записей
  эпизода.

### Modified Capabilities
<!-- none: новая подсистема (перенос компонента) -->

## Impact

- launcher/метрики получают исходы эпизодов, пригодные для L*/detection;
- слова агента не являются доказательством (FR-1.18).
