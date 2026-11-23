"""Component `journal`: unified event and cost journal per component, on lab.chain.

- `schema` — component registry and sides, closed event vocabularies, record checks;
- `log` — `EventLog`/`ComponentWriter`, hash chain over a lab.chain JSONL file,
  trajectories for rerun comparison;
- `costs` — cost summary by sides/components/traffic/episodes and money conversion.
"""

from .costs import RATE_PRESETS, Rates, compute_usd, defender_bucket, per_episode_means, summarize
from .log import (
    ComponentWriter,
    EventLog,
    LoadedLog,
    episode_fingerprint,
    load_jsonl,
    select,
    trajectory,
    verify_chain,
)
from .schema import (
    ATTACK_OUTCOMES,
    COMPONENT_SIDES,
    COST_FIELDS,
    GUARD_SIGNALS,
    KINDS,
    POLICY_ACTIONS,
    SCHEMA,
    SIDES,
    TRAFFIC_CLASSES,
    EventLogError,
    component_class,
    side_of,
)

__all__ = [
    "ATTACK_OUTCOMES",
    "COMPONENT_SIDES",
    "COST_FIELDS",
    "GUARD_SIGNALS",
    "KINDS",
    "POLICY_ACTIONS",
    "RATE_PRESETS",
    "SCHEMA",
    "SIDES",
    "TRAFFIC_CLASSES",
    "ComponentWriter",
    "EventLog",
    "EventLogError",
    "LoadedLog",
    "Rates",
    "component_class",
    "compute_usd",
    "defender_bucket",
    "episode_fingerprint",
    "load_jsonl",
    "per_episode_means",
    "select",
    "side_of",
    "summarize",
    "trajectory",
    "verify_chain",
]
