## ADDED Requirements

### Requirement: Env template with defaults and no model names
Репозиторий SHALL содержать `.env.example` с рабочими дефолтами (URLs
сервисов 9410–9415, пути SQLite, совпадающие с дефолтами кода), и SHALL NOT
задавать имена моделей дефолтами: ростер — `frozen/llm.json`
(замороженная характеристика), внешние модели — только через
`allow_remote_llm` без записи в заморозку. Ключи API в шаблоне — только
плейсхолдеры.

#### Scenario: Defaults are usable as .env
- **WHEN** `.env.example` скопирован в `.env` без правок и сервисы подняты
  вручную (не через dev.py)
- **THEN** URLs и хранилища совпадают с дефолтами кода; сервисы стартуют

#### Scenario: No model names in defaults
- **WHEN** шаблон прочитан
- **THEN** в дефолтах нет имён моделей; секция Live-LLM содержит
  плейсхолдеры `<имя-модели-у-прокси>` и напоминание про ростер и
  remote-флаг

### Requirement: dev.py loads .env without overriding
`scripts/dev.py` SHALL загружать `.env` из корня репозитория в `os.environ`
(stdlib-парсер: KEY=VALUE, одинарные/двойные кавычки, префикс `export`,
inline-`#`-комментарии) и SHALL NOT перекрывать переменные, уже заданные в
окружении. Этот uv не грузит `.env` при `uv run`, поэтому dev-режим делает
это сам.

#### Scenario: Live-LLM vars reach services
- **WHEN** `.env` содержит `LAB_CUSTOMER_LLM_*`/`RESEARCH_LLM_*` и запущен
  `uv run python scripts/dev.py`
- **THEN** все 6 сервисов получают переменные; UI показывает имена
  remote-моделей в `/api/meta`

#### Scenario: Explicit env wins
- **WHEN** переменная задана и в окружении, и в `.env`
- **THEN** значение из окружения сохраняется
