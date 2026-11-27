## ADDED Requirements

### Requirement: Model time is exposed to the agent
The `read_ticket` operation SHALL return `model_time`, the shop's model time
(`meta.now` of the world), as trusted read data. The agent prompt SHALL instruct
using `model_time` for all date arithmetic and SHALL forbid guessing the current
date. The set of five tools (FR-1.11) SHALL remain unchanged.

#### Scenario: Window arithmetic has an anchor
- **WHEN** the agent needs the refund window age of an order
- **THEN** it computes days from `read_ticket.model_time` and the order's
  `delivered_at`, not from an assumed date

#### Scenario: Untrusted context is unchanged
- **WHEN** the context-provenance guard extracts fragments from `read_ticket`
- **THEN** only `messages` remain untrusted context; `model_time` is trusted data
