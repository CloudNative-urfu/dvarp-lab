## Why

Перенесённая защита ценна только при переносе и её тестов: набор тестов
прототипа (agent, configs, evaluator, executor, guard_contract,
guard_plugins, guard_policy, llm, tools) — этоexecutable-спецификация
FR-1.x/NFR-2.x; без него «перенос как есть» не проверяем.

## What Changes

- `tests/` — порт тестов защиты из прототипа: test_agent, test_configs,
  test_evaluator, test_executor, test_guard_contract, test_guard_plugins,
  test_guard_policy, test_llm, test_tools;
- `tests/_env.py` — общий тестовый окруженческий слой;
- правки перенесённых модулей — только под тестовый контур
  (configs/process, db, evaluator/harness, policy/testkit, plugins/evaluate).

## Capabilities

### New Capabilities
- `shop-test-suite`: порт набора тестов защиты из прототипа.

### Modified Capabilities
<!-- none: тестовый слой -->

## Impact

- перенесённый код защиты проверяется тем же набором, что в прототипе;
- последующие сервисные тесты (test_shop_service и др.) дополняют слой.
