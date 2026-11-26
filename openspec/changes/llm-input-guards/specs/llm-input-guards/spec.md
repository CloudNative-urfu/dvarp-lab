## ADDED Requirements

### Requirement: LLM guards at the input position
The frozen set SHALL contain `g_in_qwen`, `g_in_granite` and `g_in_llama`: one LLM
detector (`qwen3guard-gen-4b`, `granite-guardian-3.1-2b`, `llama-guard-3-8b`) installed
only at `input` with the reaction policy of `g_in`. They SHALL be selected through the
ordinary `configs` axis; no separate detector axis exists.

#### Scenario: Same position, same policy
- **WHEN** `g_in`, `g_in_oss` and the three LLM configurations are compared
- **THEN** they differ only in the plugin at `input`, and their policy tables are equal

### Requirement: Guard model endpoint
The shop SHALL give every model-backed guard a live chat model on
`LAB_GUARD_LLM_BASE_URL`, addressed by the plugin's pinned `model` parameter, and
SHALL reject `/configure` of such a configuration with 400 when the endpoint is unset.
A non-local guard endpoint SHALL mark the run remote.

#### Scenario: Endpoint missing
- **WHEN** `/configure` is called with `g_in_llama` and `LAB_GUARD_LLM_BASE_URL` is empty
- **THEN** the shop answers 400 naming the variable

### Requirement: Guard token budget in the manifest
The campaign manifest SHALL record, per configuration with LLM guards, the per-episode
call cap (stages × turns), the output-token cap (plugin `max_tokens` × calls) and its
price under `guard_tariff`.

#### Scenario: Budget 8 on g_in_granite
- **WHEN** a campaign with `budget: 8` includes `g_in_granite`
- **THEN** `guard_budget.g_in_granite` shows 8 calls and 64 output tokens per episode
