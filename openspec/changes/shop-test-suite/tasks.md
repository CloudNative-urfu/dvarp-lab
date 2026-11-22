## 1. Tasks

- [x] port-defense-tests `tests/` — порт набора защиты: agent, configs, evaluator, executor, guard_contract, guard_plugins, guard_policy, llm, tools
- [x] test-env `tests/_env.py` — общий тестовый слой окружения
- [x] test-contour Правки перенесённых модулей под тестовый контур (configs/process, db, evaluator/harness, policy/testkit, plugins/evaluate)

- [x] service-tests `tests/test_shop_service.py` — барьер /turn, reset/configure, снимки
- [x] tests-adapted Перенесённые тесты адаптированы к сервисному слою (порты, env)

- [x] ruff-format agent_demo приведён к ruff format (стиль; поведение без изменений)
