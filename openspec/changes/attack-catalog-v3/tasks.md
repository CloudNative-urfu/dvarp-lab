# Tasks

## 1. Tasks

- [x] frozen `tactics.json`: 70 методов (8 + 62), схема `dvarp.tactics/2`
- [x] frozen `darp_corpus_v3.jsonl` (124 записи atk-29…152) + `MANIFEST_v3.json`
- [x] test состав реестра (70, идентификаторы 1…152), манифест ↔ jsonl,
  иллюстрация ↔ запись 1:1
- [x] docs agent-manual: каталог закрыт, калибровка открыта

## 2. Validation

- [x] ruff (check + format) зелёный
- [x] `uv run pytest` полный набор зелёный
- [x] `openspec validate --all` зелёный
- [x] техправка: `scripts/smoke.py` пинит `direct_task` — ось `tactics` (all = 70 после каталога) раздувала объём смока до 1610 > guard 1000
- [ ] калибровка desmitry (живая LLM): прирост V(g0) — открытый пункт #4
