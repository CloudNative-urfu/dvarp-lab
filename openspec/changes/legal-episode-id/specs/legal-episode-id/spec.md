## ADDED Requirements

### Requirement: Legal episode id carries the cell's scenario signature
`legal_episode_id` SHALL include the same cell scenario signature
(`attack_signature`) as the paired attack id, differing only in the L/A marker:
`{run}-L{i}-{goal}-{style}-{tactic}-s{seed}`. The manifest SHALL reference this
id, and the launcher SHALL read the leg outcome from the final row of that id.

#### Scenario: Unique per cell
- **WHEN** a campaign runs several cells with the same run, style and seed
- **THEN** every cell's legal leg gets a distinct episode id

#### Scenario: Pair parity
- **WHEN** a pair finishes
- **THEN** legal and attack ids share the signature and differ only in L/A
