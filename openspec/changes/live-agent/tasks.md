## 1. Tasks

- [x] launcher `allow_remote` для attacker-модели кампании и в probe()
- [x] axes set-режим модельных осей допускает off-roster имена при
  `allow_remote_llm` (не-модельные оси — по-прежнему строго frozen)
- [x] shop `/configure` пропускает ростер при `LAB_ALLOW_REMOTE_LLM=1`
  (env shop-процесса, как у агента в llm/settings.py)
- [x] shop `_agent_model()`: live через `RESEARCH_LLM_*` при заданном
  base_url, иначе stub; параметры fail-closed при неизвестном размере
- [x] llm `ChatModel.sink`: пара запрос→ответ в `raw.llm_calls` → кассеты
  `role: agent`; буфер очищается после успешной доставки; барьер /turn не
  тронут
- [x] ui `/api/meta` → `remote_models` из env (без ключей/base_url);
  подстановка имён в форме запуска; `ProbeIn.allow_remote_llm` → launcher
- [x] lab/modelspec `params_b: float | None`
- [x] tests configure-bypass, probe off-roster, attacker off-roster,
  set-mode, ui remote_models/passthrough (+6 к базовому набору)
- [x] verify живой прогон на прокси (AITunnel, qwen3.8-flash): клиент и
  атакующий живые, защитник live, кассеты `role: agent`, метрики с
  include_remote
- [x] verify `uv run pytest` зелёный; хуки pre-commit зелёные
