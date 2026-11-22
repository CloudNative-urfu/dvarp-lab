## 1. Tasks

- [x] guard-contract `services/shop/guards/contract/` — единый контракт плагина: вход с контекстом и происхождением (FR-1.5/1.6), сигнал и затраты (FR-1.7), пассивность (FR-1.8), реестр
- [x] executor `services/shop/guards/executor.py`, `boundary.py` — граница безопасности, одинаковая во всех конфигурациях (FR-1.13/1.14)
- [x] plugins `services/shop/guards/plugins/` — rules, textnorm, oss_deberta (выключен по умолчанию, NFR-2.4), builtin, adapters
- [x] policy `services/shop/guards/policy/` — конвейер, реакции isolate/escalate/terminate, testkit
- [x] tools `services/shop/guards/tools/` — пять инструментов агента (FR-1.11): specs, toolbox
- [x] llm-client `services/shop/llm/` — settings, backends, limits, factory, usage_estimate (NFR-2.5/2.6)
- [x] channel `services/shop/channel/` — legal_user, llm_user, proposal_contract, endpoints
- [x] manual-queue `services/shop/manual_queue/` — аналитическая модель ручной очереди (FR-1.15/1.16, ревизия dvarp#18)

- [x] agent `services/shop/agent/` — агент возвратов поверх llm-клиента: profiles, prompt, claims, factory, stub
- [x] tests-agent `tests/test_agent.py` — FR-1.9/1.10/1.12, NFR-2.7, детерминизм stub

- [x] stub-concat Скрытая конкатенация строк в stub-агенте устранена (ruff; поведение без изменений)
