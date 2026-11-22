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

## ADDED Requirements

### Requirement: Shared pair style in attacker prompt
Стиль общения пары SHALL задаваться в обеих ногах: легальному клиенту —
стиль из `frozen/styles.json`, атакующему — тон-клауза в system-промпт при
сохранении корпусной стартовой реплики (тактика — механизм, стиль — тон).
Записи filter пинят `raw.style`; иначе тон становится конфаундом детекции
(инвариант 8).

#### Scenario: Style in both legs
- **WHEN** пара прогонов ведётся в стиле s
- **THEN** легальная нога и атакующий промпт несут один и тот же тон;
  стартовая реплика атакующего остаётся корпусной

#### Scenario: Style pinned in raw
- **WHEN** атакующий эпизод пишет сырьё
- **THEN** записи содержат `raw.style` = стиль пары

### Requirement: Extended social tactics corpus
Расширенный корпус SHALL добавлять социальный сектор тактик (atk-21…28:
third_party_emergency, authority_impersonation) — `darp_corpus_v2_ext.jsonl`
с манифестом `MANIFEST_ext.json` (sha256, fail-closed); реестр тактик
переgroup по секторам, launcher берёт расширенную ось.

#### Scenario: Ext manifest enforced
- **WHEN** расширенный корпус не совпадает с манифестом
- **THEN** загрузка падает, атаки не стартуют

#### Scenario: Social tactics available
- **WHEN** кампания выбирает тактику atk-21…28
- **THEN** стартовый промпт разрешается из расширенного корпуса
