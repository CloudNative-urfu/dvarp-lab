# Происхождение подсистем (карта вклада)

dvarp-lab — перепись полигона с нуля; git-история лабы не переносила авторов
прототипа (решение «переписать без лишнего»). Эта карта восстанавливает
происхождение подсистем и вклад команды по истории прототипа
(`dvarp-prototype @ d5828df`) и репо-распила.

| Подсистема в dvarp-lab | Первоисточник (прототип) | Автор работы |
| --- | --- | --- |
| БД магазина v3 (`services/shop/db.py`), seed-CSV (`services/shop/seed/`), детерминированная генерация | `state_store` v3 audit schema, CSV seed, deploy manifest (прототип #38/#43, коммит `a0e1d20`); agent DB verification / v3 audit writes (#39, `480b340`); доки v3 (#54, `b0763c2`) | **sser1to (Никита Лецколюк)** — коммиты с его авторством в этой истории: `feat(shop): port config matrix…` см. ниже; БД-коммиты переписаны на него |
| Исполнительные права / audit writes (`services/shop/guards/executor/`) | executor boundary-1/2/2r + v3 audit writes (#39) | sser1to (v3-часть) + axstiz (ядро) |
| Конфигурационная матрица (`services/shop/configs/`, `frozen/configs/` — 24 конфига) | config matrix (#32, `2fd02e3`) | **desmitry (Dmitry Sergeevich)** — коммиты `feat(shop): port config matrix / corpus v2 / evaluator / event log journal` |
| Корпус атак v2 (`services/shop/corpus/`, `frozen/corpus/`) | corpus v2 (#32) | **desmitry** |
| Внутренний журнал (`services/shop/journal/` — costs/schema/log) | порт `event_log` (#32) | **desmitry** |
| Оценщик (`services/shop/evaluator/`) | evaluator (#32) | **desmitry** |
| Демо-обвязка (`services/shop/agent_demo/`, patient) | agent_demo + patient (#32) | **desmitry** |
| Канал и легальный клиент (`services/shop/channel/`, `llm_user`) | channel + правки llm_user (#74/#75) | axstiz (в т.ч. правки под именем «Матвей Вахрушев» — это один человек) |
| Guard-стек (`services/shop/guards/`: contract, plugins, policy, executor-ядро, tools) | ревизии защиты прототипа | axstiz + агенты |
| Agent, LLM-клиент, pay_emu, repro, lab/, launcher, ui, filter, metrics, attack | новая перепись лабы | axstiz + агенты |
| traffic_svc | порт из прототипа в `polygon-traffic` — **в lab переписан с нуля**; snapshot-bound концепт и реализация: **Alexander (BruhWhyMeHaveNoIdea)** (#73, `dfa9e0e`) | Alexander (в распиле) |

Вклад по строкам (numstat прототипа, перенесённые пакеты): axstiz ~20 900,
sser1to ~1 412, desmitry ~1 346, Матвей Вахрушев = axstiz (+277 в channel/llm_user),
Alexander +345 (traffic_svc — в распиле).

Исторические коммиты авторов сохранены в:
- `dvarp-prototype` (полная история);
- репо-распиле: `ss-refund-shop` (git-filter-repo сохранил авторства: `9626561`,
  `54192dd`, `fafc546` — sser1to), `polygon-traffic` (Alexander, Матвей).

Правки этой карты — только факультативные дополнения; существующие строки не
переписывать (это документ происхождения, не бортовой журнал).
