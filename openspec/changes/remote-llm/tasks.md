## 1. Tasks

- [x] flag Флаг allow_remote_llm в спецификации осей / CLI --allow-remote-llm и в UI (галочка)
- [x] nominal `lab/nominal.py` — remote-эндпоинты допускаются только с флагом
- [x] manifest-pin Пин `remote_llm: true` в манифесте прогона
- [x] raw-pin Пин `raw.remote_llm=true` в каждой записи filter
- [x] metrics-skip Метрики исключают remote-эпизоды по умолчанию; include_remote — явная опция /compute
- [x] tests `tests/test_remote_llm.py` — тройной guard
