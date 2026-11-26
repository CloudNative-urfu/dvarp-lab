## MODIFIED Requirements

### Requirement: Axis specification
Оси кампании SHALL задаваться JSON-спецификацией: каждая ось — режим
`point | range | all | all_limited`. Перечислимые оси (goals, configs,
styles, tactics c фильтром split: dev|holdout, agent_models,
attacker_models) берутся из frozen-наборов (отсортированные; range —
непрерывный срез); технический режим `set` — явный список для CLI и
пресетов. Числовые оси (episodes, seeds) не допускают режим `all`
(неограничены). Ячейка кампании — config × goal × style × tactic ×
agent_model × attacker_model × seed: ось мира один, прежние оси
миров/когорт выпали; сид остаётся для детерминизма прогона, а не для
выбора данных.

#### Scenario: Axis resolution
- **WHEN** спецификация осей разрешается
- **THEN** каждая ось даёт отсортированный конечный список значений;
  `all` на числовых осях запрещён

#### Scenario: Goal axis
- **WHEN** ось goals задана режимом all/point/set
- **THEN** значения берутся из `frozen/corpus/goals.json`

### Requirement: Run manifest with pins
Прогон SHALL пиниться манифестом `runs/<run_id>/manifest.json`: run_id,
оси кампании (включая goals), budget, seeds, `model_spec` агента и
атакующего раздельно, версия мира (`world` + `dataset_hash` — пин
замороженного мира; снапшот пары — от мира). run_id вида
`{configs}-s{seed}-{timestamp}` — читаемый и уникальный.

#### Scenario: Manifest reproducibility
- **WHEN** прогон записан в runs/
- **THEN** по манифесту восстанавливаются конфиг, сид, цели и модели
  ячейки, а также версия мира

### Requirement: Seed loop
Сиды SHALL перебираться по оси: по умолчанию один сид; диапазон сидов —
повторение ячеек для детерминизма прогона (мир один и от сида не зависит,
инвариант 8b в ревизии «один мир»); каждая ячейка — полный парный прогон с
манифестом.

#### Scenario: Seed repeat
- **WHEN** ось seeds задана диапазоном
- **THEN** ячейки повторяются с разными сидами при одном и том же мире
