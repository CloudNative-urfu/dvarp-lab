## MODIFIED Requirements

### Requirement: Shop service endpoints
shop_svc SHALL предоставлять контракты из `docs/api.md`: `POST /reset
{seed}` (сброс к замороженному миру; сид детерминирует прогон, данные не
меняет; ответ `{ok, db_version, world, dataset_hash}`), `POST /configure
{config_name, agent_model}` (применение конфигурации из frozen; не проходит
номинальную проверку → 400), `GET /snapshot/{snapshot_id}` и
`POST /snapshot/restore {snapshot_id}`. `POST /turn` SHALL принимать
опциональный `goal`: для attack-эпизода заказ претензии определяется целью
(цель → заказ мира из реестра целей; фиктивный заказ → тикет без заказа);
для legal-эпизода тикет привязывается к фиксированному всегда-возвратному
заказу легального кейса.

#### Scenario: Configure validates nominally
- **WHEN** /configure получает конфигурацию, не проходящую номинальную
  проверку
- **THEN** ответ 400, конфигурация не применена

#### Scenario: Snapshot roundtrip
- **WHEN** снимок снят и восстановлен
- **THEN** БД возвращена в исходное состояние пары

#### Scenario: Goal binds the attack ticket
- **WHEN** /turn открывает attack-эпизод с целью, ссылающейся на заказ мира
- **THEN** тикет эпизода привязан к заказу цели; неизвестная или пропущенная
  цель — ошибка 400

## ADDED Requirements

### Requirement: Roles outside the shop DB
Привязка ролей (legal/attack) SHALL жить в манифесте мира (файл
`frozen/seed_worlds/…/manifest.json`, клиент → роли → заказы), а не в БД
защитника: shop_svc читает манифест при /reset и при открытии эпизода. В БД
магазина SHALL не оставаться ни одного следа роли/атакующего
(тест-инвариант чистоты БД); манифест мира не пишется в meta.

#### Scenario: DB purity
- **WHEN** БД сброшена к миру и эпизоды проведены
- **THEN** ни одна таблица БД не содержит роль, метку атакующего или
  привязку ролей

#### Scenario: Both roles on client A
- **WHEN** открываются legal- и attack-эпизоды
- **THEN** оба привязаны к единственному клиенту A из манифеста мира
