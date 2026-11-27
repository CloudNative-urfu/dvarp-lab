## ADDED Requirements

### Requirement: Methods registry with illustrations
`frozen/corpus/tactics.json` SHALL use schema `dvarp.tactics/2`: every method has a
`description`, `illustrations` taken from its corpus entries with placeholders
replaced by bracketed claim facts, the compatible `goals` and the source `entries`.
Every attack entry atk-01…atk-28 SHALL be the illustration of exactly one method.

#### Scenario: Method in the attacker prompt
- **WHEN** the attack service builds the prompt for `role_switch`
- **THEN** the system prompt holds the method description and its illustrations as
  examples, and no corpus placeholder remains

### Requirement: Model-written attacker opening
The LLM attacker SHALL write its first message itself from the system prompt (claim,
method, style). An empty answer or DONE SHALL fall back to the rendered goal claim.
The stub attacker SHALL open with the goal claim.

#### Scenario: Attacker model answers DONE at the start
- **WHEN** the attacker model answers DONE to the first request
- **THEN** the first turn sent to the shop is the rendered goal claim
