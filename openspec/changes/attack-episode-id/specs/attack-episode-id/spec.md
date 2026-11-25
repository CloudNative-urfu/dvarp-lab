## ADDED Requirements

### Requirement: Attack episode id covers the cell's scenario axes
The launcher SHALL build the attacking episode_id and its derived seed from every
scenario axis of the cell (every axis except config, agent/attacker model and
seed), so that cells that differ in any scenario axis never share an attacking
id. The legal episode_id SHALL stay `{run_id}-L{i}-{style}-s{seed}`.

#### Scenario: Full grid of styles and tactics
- **WHEN** a campaign runs every style × every tactic with two episodes
- **THEN** all attacking episode_ids and seeds are distinct, legal ids repeat only per (style, i), and every pair has both legs

#### Scenario: New axis
- **WHEN** a cell gains a new scenario axis such as goal
- **THEN** its value appears in the attacking episode_id without changing the id code
