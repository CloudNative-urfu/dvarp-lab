## ADDED Requirements

### Requirement: Methods catalog v3 (70 methods)
`frozen/corpus/tactics.json` SHALL use schema `dvarp.tactics/2` and contain
**70 methods**: the 8 base methods plus the 62-method catalog v3 authored for
dvarp-lab#52. Every method has a `description`, `illustrations` taken from its
corpus entries (placeholders replaced by bracketed claim facts), compatible
`goals` and source `entries` (atk-01…atk-152: base corpus, ext and catalog v3
`darp_corpus_v3.jsonl` with `MANIFEST_v3.json` sha256 manifest). Every catalog
entry SHALL be the illustration of exactly one method.

#### Scenario: Method in the attacker prompt
- **WHEN** the attack service builds the prompt for any of the 70 methods
- **THEN** the system prompt holds the method description and its illustrations
  as examples, and no corpus placeholder remains

#### Scenario: Catalog v3 manifest integrity
- **WHEN** `darp_corpus_v3.jsonl` is checked against `MANIFEST_v3.json`
- **THEN** the file sha256 and every entry hash match (fail-closed artifact,
  ext precedent, outside `load_corpus()`)
