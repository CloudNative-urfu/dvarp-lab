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
