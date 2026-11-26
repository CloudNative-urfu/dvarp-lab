## 1. Tasks

- [x] registry: `g_in_qwen` / `g_in_granite` / `g_in_llama` с политикой `g_in`; адаптеры допущены в `MEASURED_ADAPTERS`
- [x] shop: модели LLM-гвардов из `LAB_GUARD_LLM_BASE_URL`, 400 на `/configure` без эндпоинта, remote-маркировка
- [x] launcher: `guard_budget` в манифесте кампании
- [x] frozen: три конфигурации и записи lock
- [x] tests: состав матрицы, отклонение выключенного адаптера (presidio-pii)
- [x] пилот на локальном эндпоинте (llama-server, три модели-детектора)
