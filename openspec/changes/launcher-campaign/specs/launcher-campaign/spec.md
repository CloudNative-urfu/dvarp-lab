## ADDED Requirements

### Requirement: Matrix orchestrator
launcher SHALL перебирать ячейки кампании (config × style × tactic ×
agent_model × attacker_model × seed) и вести каждую ячейку в фиксированном
порядке: номинальная проверка → `/reset {seed}` → `/configure` →
`/snapshot` → легальный эпизод → `/snapshot/restore` → атакующий эпизод →
`/snapshot/restore`. Провал номинальной проверки останавливает кампанию.

#### Scenario: Cell order
- **WHEN** ячейка кампании запущена
- **THEN** порядок вызовов сервиса соответствует схеме; Restore между
  ногами пары не убирается (инвариант 8)

### Requirement: Run manifest with pins
Прогон SHALL пиниться манифестом `runs/<run_id>/manifest.json`: run_id,
оси кампании, budget, seeds, `model_spec` агента и атакующего раздельно.
run_id вида `{configs}-s{seed}-{timestamp}` — читаемый и уникальный.

#### Scenario: Manifest reproducibility
- **WHEN** прогон записан в runs/
- **THEN** по манифесту восстанавливаются конфиг, сид и модели ячейки

### Requirement: Smoke script
`scripts/smoke.py` SHALL поднимать все сервисы во временных каталогах,
прогонять кампанию до конца и гасить сервисы; после смока следов в рабочих
каталогах нет.

#### Scenario: Clean smoke
- **WHEN** сквозной смок завершён
- **THEN** стенд проверен целиком, временные каталоги удалены

## ADDED Requirements

### Requirement: Axis specification
Оси кампании SHALL задаваться JSON-спецификацией: каждая ось — режим
`point | range | all | all_limited`. Перечислимые оси (configs, styles,
tactics c фильтром split: dev|holdout, agent_models, attacker_models)
берутся из frozen-наборов (отсортированные; range — непрерывный срез);
технический режим `set` — явный список для CLI и пресетов. Числовые оси
(episodes, seeds) не допускают режим `all` (неограничены).

#### Scenario: Axis resolution
- **WHEN** спецификация осей разрешается
- **THEN** каждая ось даёт отсортированный конечный список значений;
  `all` на числовых осях запрещён

#### Scenario: Tactic split filter
- **WHEN** ось tactics задана с фильтром split
- **THEN** берутся только тактики этого сектора (dev/holdout)

### Requirement: Volume guard
Объём кампании SHALL проверяться до запуска: сверх guard (1000 эпизодов) —
запрос явного `confirm: true`; объём (cells × episodes) отдаётся до старта
для оценки.

#### Scenario: Guard without confirm
- **WHEN** объём превышает guard и confirm не задан
- **THEN** кампания не стартует, возвращается needs_confirm с объёмом

### Requirement: Seed loop
Сиды SHALL перебираться по оси: по умолчанию один сид, диапазон — перебор
«миров» (seed_spread, инвариант 8b); каждая ячейка мира — полный парный
прогон с манифестом.

#### Scenario: Seed spread
- **WHEN** ось seeds задана диапазоном
- **THEN** ячейки повторяются по «мирам» с сохранением парности
