## Why

Issue: [CloudNative-urfu/dvarp-lab#10](https://github.com/CloudNative-urfu/dvarp-lab/issues/10).

Метрики читают `raw.verdict` и `raw.guard_signals`, но живой путь их не
производил: оценщик вызывался только из demo-харнесса и тестов. V, R, E и
детекция были нулями для всех конфигов. Исход ноги в манифесте угадывался по
подстрокам `session_status` и всегда был `closed`.

## What Changes

- shop при открытии эпизода сам строит эталон (`services/shop/evaluator/live.py`)
  и снимает стартовое состояние; на каждом `/turn` пишет в запись
  `raw.verdict` {violation, violations, outcome, task_status, escalated} и
  `raw.guard_signals` {signal: count} за ход;
- новая таблица filter `episode_finals` и `POST /finalize`: одна финальная
  строка на эпизод (verdict, счётчики сигналов, пин model_spec, run_id, seed,
  remote). shop ставит её в ту же очередь доставки, что и записи (#16), при
  закрытии эпизода или перед `/reset` и `/snapshot/restore`;
- metrics берут verdict и сигналы эпизода из `episode_finals`, если строка есть,
  иначе из трейса; формулы не меняются;
- `GET /finals/{episode_id}`: launcher пишет в манифест структурный исход ноги;
  `outcome_of` и лексические списки удалены, симуляции отдают только конец цикла
  (`session_closed`, `budget_exhausted`, `attacker_stopped`, `turn_limit`);
- канарейка утечки системного промпта: слот в промпте агента, поля `leak` и
  `leak_turns` в финале эпизода (вне словаря исходов канона).

## Capabilities

### New Capabilities
- `live-verdict`: вердикт оценщика и финальная строка эпизода в живом пути.

### Modified Capabilities
<!-- shop-evaluator: оценщик вызывается из shop_svc; metrics-svc: финалы поверх трейса -->

## Impact

- Ветка стоит поверх #16 (очередь доставки и события-дельты).
- Канарейка: `LAB_PROMPT_CANARY` из env прогона, иначе синтетическая на каждый
  `/reset`; `prompt_sha256` агента теперь считается по промпту со слотом.
  Доля утечек в metrics не агрегируется: поле лежит в финалах.
