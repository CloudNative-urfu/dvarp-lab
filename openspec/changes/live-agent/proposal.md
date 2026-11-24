## Why

Remote-верификация контура была половинчатой: launcher пропускал off-roster
имена только для agent-модели кампании, но `probe()` и attacker-модель
падали на KeyError, shop `/configure` отвергал off-roster пины даже с
remote-флагом, `set`-режим осей не принимал внешние имена. Живой защитник
(агент) вообще не был подключён: `_agent_model()` строил только stub, а его
вызовы модели не попадали в кассеты (`raw.llm_calls`), что нарушало
инвариант «каждый вызов модели — строкой в кассете». Для проверки конвейера
на живом прокси (не для статьи) нужен полный контур: атакующий, probe,
защитник — с пином remote-verification.

## What Changes

- `launcher/campaign.py`: `allow_remote` прокидывается в attacker-модель
  кампании и в probe() (агент и атакующий);
- `launcher/axes.py`: `set`-режим модельных осей допускает off-roster имена
  при `allow_remote_llm` (point-режим уже умел);
- `services/shop/app.py`: `/configure` при `LAB_ALLOW_REMOTE_LLM=1` в env
  shop-процесса пропускает проверку ростера (пин remote-verification);
  `_agent_model()` строит **live**-модель через `RESEARCH_LLM_*` при
  заданном base_url, иначе stub; сырые пары запрос→ответ защитника
  доставляются в filter (`raw.llm_calls`) и оседают кассетами;
- `services/shop/llm`: `ChatModel` получает опциональный `sink` (пара
  запрос→ответ; тексты — только в сырую БД filter, барьер не тронут);
  `settings.py` fail-closed при неизвестном размере модели в remote-режиме
  (был TypeError на `float(None)`);
- `services/ui`: `/api/meta` отдаёт `remote_models` (имена из env процесса:
  `RESEARCH_LLM_MODEL`, `LAB_ATTACKER_LLM_MODEL`; ключи/base_url не
  раскрываются); поля моделей подставляют эти имена при включённом Remote
  LLM; `ProbeIn` принимает `allow_remote_llm` (галочка Probe заработала);
- `lab/modelspec.py`: `params_b: float | None` (честный пин remote-модели
  без известного размера).

## Capabilities

### New Capabilities
- `live-agent`: живой защитник через `RESEARCH_LLM_*` и кассеты вызовов
  агента.

### Modified Capabilities
- `remote-llm`: off-roster имена моделей допускаются во всех точках входа
  (configure/probe/attacker/set-режим) под пином remote-verification; UI
  подставляет имена из env; probe-флаг проходит до launcher.
