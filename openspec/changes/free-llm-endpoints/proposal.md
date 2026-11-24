## Why

Issue: [CloudNative-urfu/dvarp-lab#7](https://github.com/CloudNative-urfu/dvarp-lab/issues/7).

Проверка локальности LLM-эндпоинтов была гейтом в двух местах
(`lab/nominal.py:check_config`, `services/shop/llm/settings.py`) и
обходилась только флагами `allow_remote_llm` / `LAB_ALLOW_REMOTE_LLM=1`.
Для тестов команде нужно запускать облачные модели без настройки флагов —
только маркировка, без запрета; финальные прогоны статьи остаются на
локальном железе.

## What Changes

- `lab/nominal.py`: гейт локальности и гейт ростера сняты; новые
  `is_local_url` (loopback) и `remote_endpoints` (не-локальные base_url из
  `RESEARCH_LLM_*`, `LAB_CUSTOMER_LLM_*`, `LAB_ATTACKER_LLM_*`);
- `services/shop/llm/settings.py`: `check_local_endpoint` →
  `check_endpoint` (только гигиена: схема http/https, без учётных данных в
  URL, есть хост); не-локальный эндпоинт агента — `remote_verification`
  (предел NFR-2.6 не применяется, размер по-прежнему fail-closed);
- маркировка автоматическая: launcher пинит `remote_llm` в манифесте по
  env-эндпоинтам; shop/traffic/attack сами ставят `raw.remote_llm` при
  не-локальном собственном эндпоинте; metrics исключают эпизод целиком,
  если remote хоть одна его запись;
- ростер не гейт: off-roster имена допускаются в осях, launcher и
  `/configure` с пином `remote-verification`;
- `allow_remote_llm` (спека/CLI/UI) и `LAB_ALLOW_REMOTE_LLM` принимаются и
  игнорируются;
- ревизия инвариантов 8c и 9 в `docs/agent-manual.md`, `docs/api.md`,
  `.env.example`.

## Capabilities

### New Capabilities
- `free-llm-endpoints`: любой http(s) эндпоинт без флагов, автоматический
  тройной guard remote-прогонов, ростер как справочник.

### Modified Capabilities
<!-- remote-llm: флаг allow_remote_llm больше не гейт (см. design) -->

## Impact

- данные статьи по-прежнему только с локальных эндпоинтов: remote-эпизоды
  исключены из метрик по умолчанию (`include_remote` — явная опция);
  канон NFR-2.5 не меняется, заявка в canon-requests не нужна;
- локальный контур сужен до loopback (раньше агент считал локальными и
  частные IP): LAN-эндпоинт маркируется remote, доступ с других машин —
  SSH-туннель на 127.0.0.1 (как в issue #84 dvarp-prototype).
