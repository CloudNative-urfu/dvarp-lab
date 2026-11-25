## 1. Tasks

- [x] evaluator `live_truth` — эталон эпизода от канала, актора и БД
- [x] shop старт-состояние и эталон на открытии; `raw.verdict`, `raw.guard_signals` за ход
- [x] filter `episode_finals`, `POST /finalize`, `GET /finals/{episode_id}`
- [x] shop финал эпизода через очередь доставки: при закрытии и перед reset/restore
- [x] metrics verdict и сигналы из финалов, иначе из трейса
- [x] launcher исход ноги из финалов; `outcome_of` и лексические списки удалены
- [x] docs `docs/api.md`
- [x] tests verdict и сигналы в записи shop; финал один на эпизод, исход для launcher; смок: финалы на все эпизоды, E и R ненулевые
- [x] leak слот канарейки в system-промпте (`AgentConfig.prompt_canary`, хеш промпта учитывает её); `leak`, `leak_turns` в финале эпизода, вне словаря исходов
