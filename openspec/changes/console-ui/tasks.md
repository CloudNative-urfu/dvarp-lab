## 1. Tasks

- [x] ui-app `services/ui/app.py` — статическая страница + /api/* (meta, volume, run, probe, status)
- [x] ui-static `services/ui/static/` — index.html, app.js, style.css (палитра консоли прототипа)
- [x] readonly-proxy Read-only прокси /api/metrics, /api/compute, /api/text, /api/chain, /api/runs
- [x] run-lock Один прогон за раз: фоновый поток, 409 на второй /api/run
- [x] tests-ui `tests/test_ui.py` — инвариант «только читатель/вызыватель»

- [x] roster-fix Атакующая модель в форме — из ростера frozen/llm.json; числовые оси — point-дефолты; фолбэк пустого ростера на ручной ввод
