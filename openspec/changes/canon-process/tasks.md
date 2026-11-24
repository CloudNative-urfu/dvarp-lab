## 1. Tasks

- [x] canon-requests Каталог `canon-requests/`: README (правила/шаблон/
  реестр, сквозная нумерация лаба с 001), `pending/`, `accepted/`
- [x] agents Раздел «Задачи, ишью и канон» в `AGENTS.md`
- [x] manual Пункт про канон и `canon-requests/` в «Запреты»
  `docs/agent-manual.md`
- [x] pr-only Дисциплина веток и PR в `AGENTS.md` (ветка
  `issue/<N>-<slug>`, ревью тимлида/саморевью, squash, линейная история) +
  требование `PR-only integration` в спеке; branch protection main —
  через API (запрет прямых пушей всем, 1 аппрув, bypass аппрува axstiz)
- [x] verify `openspec validate --all` зелёный; `uv run pytest` зелёный;
  pre-commit зелёный
