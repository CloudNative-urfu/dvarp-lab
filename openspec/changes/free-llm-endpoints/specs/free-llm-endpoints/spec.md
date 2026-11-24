## ADDED Requirements

### Requirement: Any http(s) LLM endpoint without flags
Any http(s) `base_url` SHALL be accepted for the agent, legal customer and
attacker clients without flags; only transport hygiene is enforced (scheme
http/https, a host, no credentials in the URL).

#### Scenario: Cloud endpoint starts
- **WHEN** `RESEARCH_LLM_BASE_URL` points to a public https proxy and no flags are set
- **THEN** the live client is built and the run starts

#### Scenario: Credentials in URL rejected
- **WHEN** a base_url contains `user:password@`
- **THEN** configuration fails before the first request

### Requirement: Automatic remote marking
A non-loopback LLM endpoint SHALL switch on the triple remote guard by itself:
`"remote_llm": true` in the run manifest, `raw.remote_llm=true` in records of
every service whose own endpoint is remote, and metrics skip the whole episode
by default (`include_remote` is the explicit opt-in). Local runs SHALL carry no
remote pin; the deprecated `allow_remote_llm` flag is accepted and ignored.

#### Scenario: Remote run is marked
- **WHEN** a campaign runs with a non-loopback endpoint in env
- **THEN** the manifest has `remote_llm: true` and the service records carry `raw.remote_llm`

#### Scenario: Local run is clean
- **WHEN** all endpoints are loopback or unset (stub)
- **THEN** neither the manifest nor the records are pinned remote, even with `allow_remote_llm`

#### Scenario: Article metrics stay local
- **WHEN** any record of an episode is remote and `/compute` runs without include_remote
- **THEN** the whole episode is excluded from metrics

### Requirement: Roster is a reference, not a gate
Model names outside `frozen/llm.json` SHALL be accepted on model axes, in the
launcher and in shop `/configure`, pinned honestly as
`revision="remote-verification"`, `params_b=None`. Model size (NFR-2.6) SHALL
stay fail-closed: an unknown size requires `RESEARCH_LLM_PARAMS_B`.

#### Scenario: Off-roster model
- **WHEN** a run names a model absent from the roster
- **THEN** it runs with a remote-verification model_spec

#### Scenario: Unknown size
- **WHEN** a remote agent model has no size in its name and no `RESEARCH_LLM_PARAMS_B`
- **THEN** configuration fails with a message naming `RESEARCH_LLM_PARAMS_B`
