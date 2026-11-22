## 1. Tasks

- [x] cli `launcher/__main__.py` — CLI кампании: конфиг, сид, эпизоды, compute
- [x] paired-runs Парные прогоны: /reset → /configure → /snapshot → легальный эпизод → restore → атакующий → restore
- [x] manifest `runs/<run_id>/manifest.json` — оси, budget, seeds, пин model_spec
- [x] smoke `scripts/smoke.py` — сквозной смок во временных каталогах

- [x] axes `launcher/axes.py` — режимы point/range/all/all_limited, guard объёма, seed-цикл
- [x] campaign `launcher/campaign.py` — run_campaign по спецификации осей, прогресс
- [x] tests-axes `tests/test_axes.py` + `tests/test_campaign.py` — разрешение осей, объём, пары
