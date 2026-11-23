## ADDED Requirements

### Requirement: Config registry with lock integrity
Реестр конфигураций SHALL соответствовать замороженным `frozen/configs/`:
26 конфигураций (базовая линия g0, процесс-линия g_proc, guarded-семейства
input/output/context/process/tool/layered с вариантами isolate, detect_only,
term), отпечаток файлов сверяется с `configs.lock.json` (NFR-2.10) и
учитывается границей исполнителя (FR-1.14). Изменённый, пропавший или лишний
файл SHALL обнаруживаться.

#### Scenario: Drift detection
- **WHEN** файл конфигурации изменён без обновления lock
- **THEN** проверка отпечатка сообщает о дрейфе; применение конфигурации
  fail-closed

### Requirement: Configuration application
Применение конфигурации SHALL задавать набор гвардрейлов, политику реакций,
права исполнителя и правила эскалации из спеки; конфигурация вне реестра
или с нецелым lock SHALL отклоняться.

#### Scenario: Apply by name
- **WHEN** конфигурация применяется по имени из реестра
- **THEN** активны ровно те гвардрейлы и реакции, что заданы спекой
