## 1. Tasks

- [x] flag Флаг allow_remote_llm в спецификации осей / CLI --allow-remote-llm и в UI (галочка)
- [x] nominal `lab/nominal.py` — remote-эндпоинты допускаются только с флагом
- [x] manifest-pin Пин `remote_llm: true` в манифесте прогона
- [x] raw-pin Пин `raw.remote_llm=true` в каждой записи filter
- [x] metrics-skip Метрики исключают remote-эпизоды по умолчанию; include_remote — явная опция /compute
- [x] tests `tests/test_remote_llm.py` — тройной guard

- [x] live-client Живой OpenAI-совместимый клиент: model+bearer в traffic/attack, remote-bypass в shop llm settings
- [x] env-keys Bearer-ключи только в env (LAB_CUSTOMER_LLM_*, LAB_ATTACKER_LLM_*, RESEARCH_LLM_*); env.example обновлён
- [x] nominal-proxy Номинальная проверка по настройкам клиента (base_url прокси)
- [x] tests-live `tests/test_remote_llm.py` — живой контур, ключи не в журналах
