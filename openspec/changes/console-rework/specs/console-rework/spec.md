## ADDED Requirements

### Requirement: Console form described by backend data
The console SHALL render its run and probe forms entirely from `/api/meta`:
axes with modes (point, range, set, all, all_limited), universes and defaults,
run and probe fields, presets as full axis specs, and the term dictionary.
Adding an axis, preset or term SHALL need no JavaScript change.

#### Scenario: Preset is a runnable spec
- **WHEN** a preset from `/api/meta` is sent to `/api/volume`
- **THEN** it resolves to a campaign with at least one cell

#### Scenario: Mix of configurations
- **WHEN** an axis is set to mode `set` with several values
- **THEN** the run covers exactly those values

### Requirement: One-off metrics preview
metrics_svc SHALL provide `POST /preview` with the `/compute` filters (config,
model_spec, include_probe, include_remote) that returns final metrics together
with the collected aggregates and never writes `metric_results`.

#### Scenario: Preview leaves no trace
- **WHEN** `/preview` is called
- **THEN** the response has the same L* as `/compute` would store, and `/metrics/{config}` stays empty

### Requirement: Episode dialog as text only
filter_svc SHALL provide `GET /dialog/{episode_id}`: per turn the customer or
attacker message and the agent reply, taken from channel messages, with
duplicate deliveries collapsed and no other raw field exposed.

#### Scenario: Barrier holds
- **WHEN** an episode record carries guard signals and tool events
- **THEN** `/dialog` returns only turn, channel, author and text

### Requirement: Runs view
The console SHALL list run manifests and show a run's axes, cells and episode
outcomes, opening both legs of a pair as dialogs; the live status of the
current run SHALL be polled while it runs.

#### Scenario: Pair opened from a run
- **WHEN** an episode of a cell is clicked
- **THEN** the legal and attack dialogs of that pair are shown side by side
