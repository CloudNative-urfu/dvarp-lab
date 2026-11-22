## 1. Tasks

- [x] skeleton Каталоги `services/`, `lab/`, `launcher/`, `frozen/`, `tests/`; `pyproject.toml`, `uv.lock`, README
- [x] frozen Замороженные характеристики: `configs/` (26 конфигов + `configs.lock.json`), корпус v2 (`darp_corpus_v2.jsonl` + `MANIFEST.json`), `llm.json`, `styles.json`
- [x] lab-lib Мини-либа `lab/`: chain (хеш-цепочка), cassette, seeds, modelspec, nominal, db, svc_client
- [x] services Скелеты пяти сервисов FastAPI: shop, traffic, attack, filter, metrics
- [x] openspec openspec init: schema spec-driven, контекст проекта в `openspec/config.yaml`
- [x] pre-commit `.pre-commit-config.yaml`: ruff из nixpkgs + `openspec validate --all`

- [x] api-docs `docs/api.md` — контракты эндпоинтов сервисов

- [x] ruff-scope ruff исключает `frozen/` и `local-sources/` (`pyproject.toml`)

- [x] agent-manual `docs/agent-manual.md` (инварианты) + `docs/scheme.svg` (схема полигона)

- [x] paper-runs Решение «эксперименты статьи — на dvarp-lab» зафиксировано в мануале

- [x] gitignore `local-sources/` (ссылочный клон прототипа) исключён из git

- [x] dev-stack `scripts/dev.py` — все сервисы + консоль одной командой; default probe-модели и фикс сида в campaign
