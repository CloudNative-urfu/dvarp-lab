# Free LLM Endpoints — Specification (delta: live-readiness)

## MODIFIED Requirements

### Requirement: Roster is a reference, not a gate
Model names outside `frozen/llm.json` SHALL be accepted on model axes, in the
launcher and in shop `/configure`, pinned honestly as
`revision="remote-verification"`, `params_b=None`. Model size (NFR-2.6, ревизия
2026-11-12) SHALL stay fail-closed with a single limit of 16B parameters:
an unknown size requires `RESEARCH_LLM_PARAMS_B`; models above 16B are
rejected (no 8B/12B two-tier exceptions).

#### Scenario: Off-roster model
- **WHEN** a run names a model absent from the roster
- **THEN** it runs with a remote-verification model_spec

#### Scenario: Model size limit
- **WHEN** a model is sized at most 16B (explicitly or parsed from the name)
- **THEN** it is accepted; a model above 16B is rejected with NFR-2.6 error
