## ADDED Requirements

### Requirement: Results table of stored metrics
The console SHALL open on a results table built from stored metric groups of the agent
role for every configuration in the axis universe, remote groups included, showing per
configuration the number of attacks, V, R, E and the break-even verdict with a plain
label and hint for each column. Opening the table SHALL NOT compute metrics.

#### Scenario: Remote campaign is visible
- **WHEN** metric results were stored only for remote runs
- **THEN** `/api/summary` returns their agent groups and the table marks them as cloud models not used in the paper

#### Scenario: Incomparable configuration
- **WHEN** a configuration has a different number of attacks than reference g0 of the same model
- **THEN** its row is marked as a different attack set and listed after the comparable rows

### Requirement: Episode pairs listed from manifests
ui_svc SHALL provide `GET /api/pairs` that lists episode pairs from run manifests with
run id, configuration, scenario and both legs' ids and outcomes, filtered by
configuration, attack outcome and run id, together with the configurations and runs
available for filtering.

#### Scenario: Successful attacks on the reference
- **WHEN** `/api/pairs?config=g0&attack=executed` is requested
- **THEN** only g0 pairs whose attack leg was executed are returned and `total` counts them all

### Requirement: Human labels described by backend data
`/api/meta` SHALL carry `labels` for configurations, goals, tactic descriptions,
leg outcomes with a tone, key and detection metrics, break-even verdicts and services,
so the console names everything in plain language without hardcoding it in JavaScript.

#### Scenario: Every configuration and goal is named
- **WHEN** `/api/meta` is requested
- **THEN** every configuration and goal of the axis universes has a label

### Requirement: Simple run form with advanced settings kept
The run tab SHALL ask only for configuration, goal, method and pairs per cell, each
with a description, and SHALL keep every previous control (axis modes, models, seeds,
budget, presets, probe) under collapsed advanced settings sharing the same form state.

#### Scenario: Advanced mode overrides the simple field
- **WHEN** an axis is switched to a non-point mode in advanced settings
- **THEN** the simple field for that axis says the value is set in advanced settings
