## ADDED Requirements

### Requirement: Tactics registry from frozen corpus
Реестр тактик SHALL быть заморожен в `frozen/corpus/tactics.json` и
сгруппирован из корпуса атак по осям разметки FR-1.21 (механизм, цель,
овервербальный канал). Тактика для эпизода назначается планом прогона, а не
выбирается моделью; неизвестная тактика — ошибка.

#### Scenario: Tactic by plan
- **WHEN** эпизод атаки запрошен с тактикой из реестра
- **THEN** стартовый промпт берётся из корпуса по разметке тактики

## ADDED Requirements

### Requirement: Text-only attack episode
`attack_svc` SHALL вести эпизод атаки: `POST /run-episode`
`{episode_id, config_name, agent_model, attacker_model, tactic, budget,
seed}` → `{outcome, turns, attempts}`, с сигналами `POST /start` и
`POST /stop` для launcher'а. Атакующий ходит только текстом через
`shop /turn` с `channel="attack"`, имеет бюджет ходов и НЕ имеет доступа к
БД магазина, решениям гвардрейлов и коду защиты (инвариант 2).

#### Scenario: Attacker sees only text
- **WHEN** атакующий делает ход
- **THEN** он получает только текст ответа СС; ни БД, ни решения гвардрейлов
  в его контексте нет

#### Scenario: Budget enforced
- **WHEN** бюджет ходов исчерпан
- **THEN** эпизод завершается с исходом по бюджету, ходов больше нет

### Requirement: Attack recordings pinned
Записи атакующего SHALL пинить `model_spec` атакующего и доставлять сырьё
(включая кассеты вызовов модели атакующего) в `filter /record` изнутри,
минуя текстовый канал.

#### Scenario: Attacker cassette
- **WHEN** атакующий делает вызов модели
- **THEN** пара «запрос → ответ» оседает кассетной строкой в сырой БД
