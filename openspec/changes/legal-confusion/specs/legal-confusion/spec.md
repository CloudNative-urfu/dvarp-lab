## ADDED Requirements

### Requirement: Confusion axis of the legal leg
The campaign SHALL enumerate a `confusion` axis over `frozen/corpus/confusion.json`
(`dvarp.confusion/1`): `none` (anchor, default), `forgetful`, `typo`, `tech_soup`.
Confusion is a property of the LEGAL leg only; the style stays shared by the pair.
The mode SHALL be part of the cell signature: derived seeds and episode ids of both
legs include it (unique legal episodes per mode; independent attack resamples).

#### Scenario: Default anchor keeps volume
- **WHEN** a campaign spec omits the confusion axis
- **THEN** every cell runs with `none` and the volume matches older specs

### Requirement: Honest-only confusion
Confusion events SHALL be truthful (wording changes, facts never change), rare
(one event per episode, chosen from the frozen bank by the run seed) and realistic
in frequency. The legal episode SHALL pin the mode in `raw.confusion`.

#### Scenario: Typo keeps the case intact
- **WHEN** the typo mode mangles the item name in a chat reply
- **THEN** the shop order data and other case facts are unchanged

#### Scenario: Deterministic events
- **WHEN** two stub episodes run with the same seed and mode
- **THEN** their confused replies are identical

### Requirement: Realistic honest traffic estimate
The anchor `none` SHALL preserve the saint semantics (lower-bound harm); the other
modes SHALL measure FP/R/G-tau on realistic honest traffic and SHALL be run as
separate campaign runs so per-mode metrics stay pure through the run_id split.

#### Scenario: Per-mode metrics without formula surgery
- **WHEN** confusion modes are measured
- **THEN** each run yields pure per-mode R/FP/G-tau via the existing run_id split
