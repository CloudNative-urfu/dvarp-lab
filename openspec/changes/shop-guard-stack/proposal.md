## Why

Ядро исследования — защита СС: гвардрейлы с контрактом плагинов, конвейер
политики, инструменты агента, LLM-клиент и очередь ручных разборов. Код
переносится из dvarp-prototype @ `d5828df` как есть (canon #32) —
эксперимент должен измерять ровно ту защиту, что живёт в продукте.

## What Changes

- `services/shop/guards/` — контракт плагинов (FR-1.5–1.8), исполнитель
  (FR-1.13/1.14), плагины (rules, textnorm, oss_deberta, builtin, adapters);
- `services/shop/policy/` — конвейер политики и реакции (defender);
- `services/shop/tools/` — пять инструментов агента (FR-1.11);
- `services/shop/llm/` — LLM-клиент: settings, backends, limits, factory,
  usage_estimate (NFR-2.5/2.6);
- `services/shop/channel/` — канал агента: legal_user, llm_user,
  proposal_contract, endpoints;
- `services/shop/manual_queue/` — общая очередь ручных разборов
  (FR-1.15/1.16, ревизия канона dvarp#18).

## Capabilities

### New Capabilities
- `shop-guard-stack`: перенос ядра защиты — контракт/плагины/исполнитель,
  политика, инструменты, LLM-клиент, канал, ручная очередь.

### Modified Capabilities
<!-- none: новая подсистема (перенос кода защиты) -->

## Impact

- `services/shop/` получает ядро защиты; клиентский код защиты не меняется
  (FR-1.9);
- подсистемы прототипа (isolation, svckit, state_store, pay_emu, freeze) не
  переносятся сознательно.
