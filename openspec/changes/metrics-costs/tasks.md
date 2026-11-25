# Tasks

## 1. Tasks

- [x] economics Замороженный пин `frozen/economics.json` + валидирующий
  загрузчик `services/metrics/economics.py`
- [x] extract Пост-хок разбор `raw.events`: C_ep (agent `llm_call`),
  C_guard (`guard:*` сигналы/ошибки), CPU как время; атакующий исключён
  (NFR-2.9); средние по эпизодам в `Aggregate`, `as_inputs` передаёт
  C_ep/C_guard
- [x] formulas Пины 0.0 убраны; C_manual base = пиновый C_human $2,
  диапазон (1, 2, 15); docstring ревизован
- [x] app Строки `C_ep`, `C_guard`, `C_guard_cpu_ms` в метриках
- [x] tests golden под C_manual=2 (test_metrics_golden, test_metrics_service);
  cost-тесты: пин, разбор затрат, end-to-end затраты → L* (test_metrics_costs)
- [x] spec Дельта спеки (`specs/metrics-svc/spec.md`)

## 2. Validation

- [x] `uv run pytest` — 407 passed
- [x] `openspec validate --all` зелёный
- [x] ruff (check + format) зелёный

## 3. Out of scope

- Аналитическая очередь и ревизия члена ухода клиентов — issue #12
  (+ canon-request);
- LLM-гварды в матрице — issue #21.
