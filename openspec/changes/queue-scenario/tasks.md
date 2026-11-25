# Tasks

## 1. Tasks

- [x] queue `services/metrics/queue.py`: Эрланг B/C (санити прототипа),
  сценарий (ревейт p_att, ρ₀, якорь), отвал, churn_member
- [x] economics Секция `queue` в `frozen/economics.json` + валидация и
  `queue_defaults` (base p_att = середина сценариев) в загрузчике
- [x] extract Доли эскалаций раздельно (E_A/E_L), `ql_abandon` (чистая
  вероятность), состояние очереди в `Aggregate`
- [x] formulas Цена `C_churn` (10/20/40) в `Prices`/`PRICE_RANGES`; член
  `churn` в `terms()` и `numerator()`; docstring ревизован
- [x] app Строки `E_attack`, `E_legal`, `queue_*` в метриках
- [x] tests `tests/test_metrics_queue.py`: Эрланг (санити + отрицания),
  ревейт, крайние сценарии, пин, end-to-end churn → L*, границы цены
- [x] spec Дельта спеки (`specs/metrics-svc/spec.md`)

## 2. Validation

- [x] `uv run pytest` — 416 passed
- [x] `openspec validate --all` зелёный
- [x] ruff (check + format) зелёный

## 3. Out of scope

- Wilson CI / статистическая ревизия — issue #13;
- LLM-гварды в матрице — issue #21.
