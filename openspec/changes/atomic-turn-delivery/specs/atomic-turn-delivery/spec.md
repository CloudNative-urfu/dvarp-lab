## ADDED Requirements

### Requirement: Turn records survive filter failures
shop_svc SHALL give every turn record a `record_id`, keep it in the episode
outbox until filter_svc accepts it, and deliver the outbox in turn order with
retries. A failed delivery SHALL NOT mark the episode as error. `/reset` and
`/snapshot/restore` SHALL drain every outbox first and answer 503 without
resetting anything when filter_svc is unavailable.

#### Scenario: Filter down mid-episode
- **WHEN** filter_svc is down during a turn and up again on the next turn
- **THEN** both turns answer 200, filter receives both records in turn order, and the chain has no holes

#### Scenario: Restore while filter is down
- **WHEN** `/snapshot/restore` is called with undelivered records queued
- **THEN** the answer is 503 and the queued records are kept

### Requirement: Idempotent record
filter_svc `/record` SHALL accept an optional `record_id`; a repeated request
with a stored `record_id` SHALL answer `{record_id, duplicate: true}` without a
new row or chain line.

#### Scenario: Retry after lost response
- **WHEN** the same record is posted twice with one `record_id`
- **THEN** filter stores one row and one chain line

### Requirement: Turn events as delta
The `raw.events` of a shop record SHALL hold only the journal events of the
episode that no earlier record of that episode carried.

#### Scenario: No repeated events
- **WHEN** an episode has several turn records
- **THEN** no journal event appears in more than one of them
