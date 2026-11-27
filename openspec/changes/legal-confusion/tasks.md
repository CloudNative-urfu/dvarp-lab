# Tasks

## 1. Tasks

- [x] frozen `frozen/corpus/confusion.json` (`dvarp.confusion/1`): none/forgetful/typo/tech_soup
- [x] traffic: `services/traffic/confusion.py` (StubConfusion, typo-трансформы, клауза live),
  StubCustomer/LlmCustomer/run_episode, пин `raw.confusion`, валидация режима
- [x] launcher: ось confusion (default-якорь none), ячейки, сиды производных
  (legal с режимом, attack через сигнатуру), манифест-ось; UI-ось
- [x] test реестр/оси, детерминизм, якорь none = прежнее поведение, typo ≠ факты,
  одно событие за эпизод, пин raw, live-клауза, unknown → reject, кампания ×4
- [x] docs: agent-manual (инвариант 8d с «почему»), api.md, README

## 2. Validation

- [x] ruff (check + format) зелёный
- [x] `uv run pytest` полный набор зелёный
- [x] смок зелёный (default none — совместимость)
- [x] `openspec validate --all` зелёный
