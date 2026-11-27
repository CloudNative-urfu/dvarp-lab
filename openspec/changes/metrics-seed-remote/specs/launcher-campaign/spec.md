## MODIFIED Requirements

### Requirement: Campaign compute selection
Launcher SHALL передавать CLI-флаги `include_remote`/`include_probe` в
`POST /compute`, не меняя процедуру сбора. Сырой seed SHALL содержать исходный
сид группы, тогда как сэмплинг ног использует производный сид.

#### Scenario: Explicit remote compute
- **WHEN** CLI запускает кампанию с `--compute --include-remote`
- **THEN** launcher передаёт `include_remote=true` в metrics_svc

#### Scenario: Pair grouping
- **WHEN** legal и attack ноги одной ячейки используют разные производные сиды
- **THEN** сырые записи обеих ног содержат одинаковый исходный seed группы
