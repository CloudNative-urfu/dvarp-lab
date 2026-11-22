## ADDED Requirements

### Requirement: Shop service endpoints
shop_svc SHALL предоставлять контракты из `docs/api.md`: `POST /reset
{seed}` (детерминированный сброс, `{ok, db_version}`), `POST /configure
{config_name, agent_model}` (применение конфигурации из frozen; не проходит
номинальную проверку → 400), `GET /snapshot/{snapshot_id}` и
`POST /snapshot/restore {snapshot_id}`, `GET /db/readonly` (описание
read-only подключения для traffic_svc).

#### Scenario: Configure validates nominally
- **WHEN** /configure получает конфигурацию, не проходящую номинальную
  проверку
- **THEN** ответ 400, конфигурация не применена

#### Scenario: Snapshot roundtrip
- **WHEN** снимок снят и восстановлен
- **THEN** БД возвращена в исходное состояние пары

### Requirement: Turn text barrier
Ответ `POST /turn {episode_id, channel, text, turn}` SHALL содержать ровно
три поля `{text, ended, session_status}`; сырьё хода (решения гвардрейлов,
вызовы инструментов, llm_calls, снимок состояния) SHALL доставляться в
`filter /record` изнутри shop_svc, минуя ответ (инвариант 1). Добавление
поля в ответ /turn — дыра в барьере.

#### Scenario: Turn response shape
- **WHEN** /turn отвечает на ход симуляции
- **THEN** в ответе ровно три поля; сырьё в ответе отсутствует

#### Scenario: Raw delivered internally
- **WHEN** ход завершён
- **THEN** запись в filter /record создана изнутри shop_svc с пином
  model_spec
