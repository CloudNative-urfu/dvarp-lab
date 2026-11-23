## Why

Матрица конфигураций защиты — управляемая переменная эксперимента: базовые
линии (g0) и guarded-семейства (input/output/context/process/tool/layered,
с вариантами isolate/detect_only/term) должны быть единым реестром,
согласованным с замороженными `frozen/configs` и их lock-хешем. Переносится
из прототипа (#32).

## What Changes

- `services/shop/configs/registry.py` — реестр конфигураций;
- `services/shop/configs/spec.py` — спека конфигурации (гвардрейлы,
  политика, права, эскалация);
- `services/shop/configs/build.py`, `demo.py`, `process.py` — сборка
  конфигураций, demo-линия, процесс-компонент.

## Capabilities

### New Capabilities
- `shop-configs`: компонент конфигураций защиты — реестр, спека, сборка,
  согласование с frozen и lock.

### Modified Capabilities
<!-- none: новая подсистема (перенос компонента) -->

## Impact

- `shop /configure` сможет валидировать и применять конфигурации из
  frozen/configs;
- launcher перебирает конфиги осью кампании по этому реестру.
