# Shop Service — Specification (delta: live-readiness)

## MODIFIED Requirements

### Requirement: Reference endpoints
shop_svc SHALL предоставлять `POST /reset {seed}` (детерминированный сброс,
`{ok, db_version}`), `POST /configure {config_name, agent_model}`
(применение конфигурации из frozen; не проходит номинальную проверку →
400), `GET /snapshot/{snapshot_id}` и `POST /snapshot/restore
{snapshot_id}`. Connection string БД магазина SHALL не покидать
shop_svc: эндпоинт `/db/readonly` удалён; traffic_svc подключается к БД
только через `LAB_SHOP_DB_URL` (env — единственный путь, issue #17).

#### Scenario: Configure validates nominally
- **WHEN** /configure получает конфигурацию, не проходящую номинальную
  проверку
- **THEN** ответ 400, конфигурация не применена

#### Scenario: No connection string endpoint
- **WHEN** запрашивается `GET /db/readonly`
- **THEN** эндпоинт отсутствует (404); connection string БД недоступен
  по HTTP
