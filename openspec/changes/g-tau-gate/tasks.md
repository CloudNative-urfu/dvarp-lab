# Tasks

## 1. Tasks

- [x] formulas `wilson_ci` (95%), `G_TAU_THRESHOLD`/`G_TAU_INTERRUPT_ACTIONS`,
  `g_tau_gate`; docstring ревизован
- [x] extract Оракул-проверка `_false_interrupt` над `policy.decision`
  (исполненное действие); поле `false_interrupt` в `Episode`; G_tau_k/
  rate/Wilson/gate в `Aggregate`
- [x] app Строки `G_tau_k`, `G_tau_rate`, `G_tau_wilson_low/high`,
  `G_tau_gate` в метриках
- [x] tests `tests/test_metrics_gtau.py`: санити Wilson (0/10, 5/10, 1/20),
  гейт, оракул (clarify/flag/агентская эскалация не считаются),
  end-to-end G-τ через `/compute` (clean → pass, 1/4 → fail, помечена)
- [x] spec Дельта спеки (`specs/metrics-svc/spec.md`)

## 2. Validation

- [x] `uv run pytest` — 420 passed
- [x] `openspec validate --all` зелёный
- [x] ruff (check + format) зелёный

## 3. Out of scope

- `episode_finals` с `traffic_kind` — issue #10 (desmitry); экстрактор
  переключится без смены формул;
- статистический overlay (Newcombe) — вне скоупа (по issue #13).
